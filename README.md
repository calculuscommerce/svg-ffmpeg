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
src/build.mjs    legacy CLI: hand-written storyboards/*.json -> MP4 using macOS `say`
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

## Gotchas

- Animated elements must not carry a `transform=""` attribute (CSS transform overrides it) — wrap them in a positioned `<g>`.
- ElevenLabs plans cap concurrent requests (free = 2): `ELEVENLABS_CONCURRENCY`.
- A 5-minute video is ~7,000 frames; expect ~8–10 min on a laptop. Scenes render in parallel (3 pages).
