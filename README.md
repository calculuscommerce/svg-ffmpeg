# Sketchboard — explainer videos from text (SVG + FFmpeg, no video model)

Type a topic or paste content → an LLM writes a structured storyboard → ElevenLabs narrates it with word
timestamps → scenes are laid out from hand-drawn SVG templates and animated in sync with the words →
headless Chromium captures frames → FFmpeg encodes the MP4. 30 s, 1 min or 5 min videos.

```
./dev.sh                 # backend on :8010, frontend on :5173
```
First copy `backend/.env.example` to `backend/.env` and add your OpenAI + ElevenLabs keys.
Needs Node 20+, Python 3.12+ (uv), ffmpeg on PATH.

## Layout

```
frontend/        React (Vite) app: composer, progress, player, storyboard editor
backend/app/
  main.py        FastAPI routes (/api/projects, /api/voices, /api/themes, /media/*)
  jobs.py        project store (data/projects/<id>/project.json) + background pipeline
  llm.py         prompt + OpenAI call -> Storyboard (constrained to templates + asset library), lint/retry
  tts.py         ElevenLabs with-timestamps -> mp3 + [(word, start, end)]
  templates.py   scene templates: title, concept, cards, bars, steps, list, stat, flow, compare, callout, diagram, outro
  compose.py     cue phrases -> word timestamps -> absolute animation times; SRT captions
  themes.py      colour themes
renderer/render.mjs   spec.json -> MP4 (parallel scene rendering, progress on stdout, optional burned captions)
player/          deterministic SVG timeline player (seek(t)); effects: wipe, draw, pop, grow, slide, count, scalex, bob, spin, pulse…
lib/parts.svg    asset library: illustrations + ~100 icons, theme-tinted via currentColor
fonts/           Patrick Hand, Caveat
```

## API

- `POST /api/projects` `{prompt, duration: 30|60|300, voice_id?, theme?: auto|ocean|forest|sunset|berry|slate, captions?, hd?, language?}`
- `GET /api/projects/{id}` → status/progress/storyboard/scenes/video_url
- `POST /api/projects/{id}/rerender` with an edited storyboard → new project, skips the LLM
- `POST /api/projects/{id}/retry`, `DELETE /api/projects/{id}`, `GET /api/voices`

## How quality is controlled

- The LLM never free-draws whole scenes. It picks a **scene type**, fills **short slots** (labels, values, captions)
  and chooses **icons from the library**; Python templates do layout. `diagram` is the one escape hatch
  (custom SVG, validated, auto-fitted to its box, one per video).
- Every item carries a **cue** — a phrase from the narration — resolved against ElevenLabs word timestamps,
  so things appear as they are spoken. Uncued items are spread between neighbours; `rel` items follow their parent.
- Numbers like `₹1,00,000`, `12%`, `2.5 billion` become animated counters (Indian/intl grouping detected);
  `bars` are drawn to scale from the values.
- Text auto-shrinks to fit (`data-maxw`), parts auto-scale into their box (`data-fit`).
- Word budgets per duration are enforced by the lint pass (the LLM is asked to trim if over).

## Drawing-hand mode (VideoScribe / RSA-Animate look)

Tick **Drawing hand on screen** (API: `"hand": true`) and, ideally, pick the black **marker** theme.
The player then draws strokes one after another with a marker hand following the pen tip
(`path.getPointAtLength`), writes text behind the marker, and carries popped-in elements onto the board with a
pinching hand. The hands are vector placeholders in `lib/parts.svg` (`hand-marker`, `hand-pinch`); to use photo
cutouts, drop PNGs into `assets/hands/` and describe the tip pixel in `assets/hands/hands.json` (see the README there).
The marker theme sets `mono`, which desaturates the whole scene so library icons read as ink drawings.

## Usage ledger

Every billable call is appended to `data/ledger.jsonl` and mirrored into the project (`backend/app/ledger.py`):
GPT-4.1 tokens (storyboard), ElevenLabs characters (voice), each gpt-image-1 call with quality (cache hits logged at
$0), and render minutes. Provider rates and credit rules are in `RATES` / `CREDIT_*` and overridable via env
(`RATE_GPT41_INPUT`, `RATE_ELEVEN_PER_CHAR`, `CREDIT_PREMIUM_MULTIPLIER`, …). Credits: 1 per finished minute in a
standard theme, 2× for premium-art themes, 0.25× for re-renders. `GET /api/usage?days=30` gives totals by service,
theme and day; `GET /api/usage/estimate?duration=60&theme=…` powers the pre-generation estimate in the composer;
each project carries `usage` (per-video breakdown). The UI has a **Usage & costs** page and a cost panel per video.

## Deployment guide

Production layout: **EC2** runs the API + renderer, **S3** holds the frontend build and generated media, **CloudFront**
serves everything from one domain (`/` → frontend bucket, `/files/*` → media bucket, `/api/*`, `/themes/*`, `/media/*`,
`/data/*` → EC2). The `deploy/` folder has every script used below.

### 1. EC2 (API + renderer)

Prerequisites: an Amazon Linux 2023 instance (x86_64; `t3.large`/`c7a.xlarge` recommended — `t3.micro` works with
swap but renders slowly), its SSH key pair, and a security group allowing 22 (your IP), 80 and 443. Point your
domain's A record at the instance's public IP if you want direct access during setup.

```bash
# on your machine, from the repo root
cp backend/.env.example backend/.env       # fill in OPENAI_API_KEY and ELEVENLABS_API_KEY
deploy/deploy.sh ec2-user@<EC2_PUBLIC_IP> ~/.ssh/<keypair>.pem
```
`deploy.sh` builds the frontend, rsyncs the source to `/opt/sketchboard`, copies `backend/.env` (only if the server has
none), then runs `deploy/install.sh` on the server, which installs nginx, Node 20, Python 3.12 + uv, a static ffmpeg,
ImageMagick, Playwright Chromium and its system deps, creates 4 GB swap, installs the `sketchboard` systemd service
(uvicorn on 127.0.0.1:8010) and the nginx site, and starts both. Re-run the same command to redeploy.

TLS for direct access (optional if you will only use CloudFront):
```bash
ssh -i ~/.ssh/<keypair>.pem ec2-user@<EC2_PUBLIC_IP> \
  'sudo certbot --nginx -d <your.domain> --non-interactive --agree-tos -m you@example.com --redirect'
```
A `certbot-renew.timer` handles renewals. Useful commands on the server: `sudo systemctl status sketchboard`,
`sudo journalctl -u sketchboard -f`, `sudo nginx -t && sudo systemctl reload nginx`.

### 2. S3 buckets

```bash
export AWS_DEFAULT_REGION=us-east-1
for b in <app>-frontend <app>-media; do
  aws s3api create-bucket --bucket $b
  aws s3api put-public-access-block --bucket $b --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
done
aws s3api put-bucket-cors --bucket <app>-media --cors-configuration \
  '{"CORSRules":[{"AllowedOrigins":["*"],"AllowedMethods":["GET","HEAD"],"AllowedHeaders":["*"],"MaxAgeSeconds":86400}]}'
```
Both buckets stay private; CloudFront reads them through an Origin Access Control (step 3).

### 3. CloudFront

1. Create an OAC: `aws cloudfront create-origin-access-control --origin-access-control-config
   Name=<app>-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3`.
2. Create the distribution with three origins — `<app>-frontend.s3.<region>.amazonaws.com` and
   `<app>-media.s3.<region>.amazonaws.com` (both with the OAC id) and the EC2 public DNS name as a custom origin
   (HTTP only, port 80). Behaviours: default → frontend bucket (CachingOptimized); `/files/*` → media bucket
   (CachingOptimized); `/api/*` → EC2 with all methods, CachingDisabled + AllViewer origin-request policy;
   `/themes/*`, `/media/*`, `/data/*` → EC2 (GET/HEAD, CachingOptimized). Custom error responses: 403 and 404 →
   `/index.html` with code 200 (SPA routing). A ready-to-edit config is in `deploy/cloudfront-distribution.json`.
3. Grant the distribution read access to each bucket:
   ```bash
   aws s3api put-bucket-policy --bucket <bucket> --policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",
     "Principal":{"Service":"cloudfront.amazonaws.com"},"Action":"s3:GetObject","Resource":"arn:aws:s3:::<bucket>/*",
     "Condition":{"StringEquals":{"AWS:SourceArn":"arn:aws:cloudfront::<account-id>:distribution/<DIST_ID>"}}}]}'
   ```
4. On the EC2 box, nginx needs a server block that answers for the EC2 DNS name and proxies the API/media paths
   (`deploy/install.sh` installs it as `/etc/nginx/conf.d/origin.conf`).

### 4. Publish the frontend

```bash
deploy/deploy-frontend.sh <app>-frontend <DIST_ID>     # builds, syncs to S3, invalidates /index.html
```

### 5. Point the backend at S3

Add to `backend/.env` on the server (then `sudo systemctl restart sketchboard`):
```
S3_BUCKET=<app>-media
MEDIA_BASE_URL=https://<DIST_ID_DOMAIN>.cloudfront.net     # or https://<your.domain> once the alias is set
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...        # or attach an instance role with s3:PutObject/DeleteObject/ListBucket on the media bucket
AWS_SECRET_ACCESS_KEY=...
```
Finished videos, captions, thumbnails and illustrations are then uploaded to `files/projects/<id>/…` and the API
returns CloudFront URLs. If the upload fails the video is still served from the server's disk.

### 6. Custom domain on CloudFront

1. Request an ACM certificate for the domain **in us-east-1** (DNS validation) and add the validation CNAME at your DNS host.
2. Once issued, add the domain as an alias on the distribution with that certificate
   (`aws cloudfront update-distribution …` with `Aliases` and `ViewerCertificate`).
3. Change the domain's DNS record to a CNAME → `<DIST_ID_DOMAIN>.cloudfront.net` and update `MEDIA_BASE_URL`.

### Checklist after deploying
`curl https://<domain>/api/health` → `{"ok":true}` · the theme gallery shows 14 thumbnails · generate a 30 s
Classic Whiteboard video and confirm its `video_url` is a `/files/projects/...` CloudFront URL.

## Gotchas

- Animated elements must not carry a `transform=""` attribute (CSS transform overrides it) — wrap them in a positioned `<g>`.
- ElevenLabs plans cap concurrent requests (free = 2): `ELEVENLABS_CONCURRENCY`.
- A 5-minute video is ~7,000 frames; expect ~8–10 min on a laptop. Scenes render in parallel (3 pages).
