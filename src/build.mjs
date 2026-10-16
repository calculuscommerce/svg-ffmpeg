#!/usr/bin/env node
// storyboard.json -> narrated MP4
//   node src/build.mjs storyboards/photosynthesis.json [--hd] [--scene N] [--still N:T]
//
//   --hd          render 1920x1080 (default 1280x720)
//   --scene N     render only scene N (1-based) -> out/<name>.sceneN.mp4
//   --still N:T   save one PNG of scene N at time T seconds to out/still.png (for debugging the art)

import { chromium } from "playwright";
import { spawn, execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync, writeSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import http from "node:http";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const sbPath = args.find((a) => !a.startsWith("--") && a.endsWith(".json"));
const flag = (n) => args.includes(`--${n}`);
const opt = (n) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : null; };
if (!sbPath) { console.error("usage: build.mjs <storyboard.json> [--hd] [--scene N] [--still N:T]"); process.exit(1); }

const sb = JSON.parse(readFileSync(path.resolve(sbPath), "utf8"));
const name = path.basename(sbPath, ".json");
const FPS = sb.fps || 24;
const SCALE = flag("hd") ? 1.5 : 1;
const W = 1280 * SCALE, H = 720 * SCALE;
const LEAD = 0.6;   // seconds of silence before narration starts
const TAIL = 1.0;   // seconds after narration ends
const FADE = 0.25;  // fade in/out per scene

for (const d of ["out", "cache"]) mkdirSync(path.join(ROOT, d), { recursive: true });

// ---------- TTS (macOS `say`; cached by text+voice+rate) ----------
function probeDuration(file) {
  return parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file]).toString());
}
function narrate(text) {
  const voice = sb.voice || "Samantha", rate = sb.rate || 165;
  const key = createHash("sha1").update(`${voice}|${rate}|${text}`).digest("hex").slice(0, 12);
  const wav = path.join(ROOT, "cache", `tts-${key}.wav`);
  if (!existsSync(wav)) {
    const aiff = wav.replace(".wav", ".aiff");
    execFileSync("say", ["-v", voice, "-r", String(rate), "-o", aiff, text]);
    execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", aiff, "-ar", "44100", "-ac", "1", wav]);
  }
  return { wav, dur: probeDuration(wav) };
}

// ---------- per-scene encode ----------
function startEncoder(outFile, D, audio) {
  const a = [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-i", audio.wav,
    "-filter_complex",
    `[0:v]fade=t=in:st=0:d=${FADE}:color=white,fade=t=out:st=${(D - FADE).toFixed(3)}:d=${FADE}:color=white,format=yuv420p[v];` +
    `[1:a]adelay=${Math.round(LEAD * 1000)}:all=1,apad=whole_dur=${D.toFixed(3)},afade=t=out:st=${(D - 0.2).toFixed(3)}:d=0.2[a]`,
    "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", D.toFixed(3),
    outFile,
  ];
  const p = spawn("ffmpeg", a, { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => p.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))));
  return { stdin: p.stdin, done };
}

// ---------- tiny static server (fetch() doesn't work over file://) ----------
const MIME = { ".html": "text/html", ".js": "text/javascript", ".svg": "image/svg+xml", ".ttf": "font/ttf" };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!f.startsWith(ROOT) || !existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": MIME[path.extname(f)] || "application/octet-stream" });
  res.end(readFileSync(f));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

// ---------- main ----------
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: SCALE });
page.on("console", (m) => { if (["warning", "error"].includes(m.type())) console.log("[page]", m.text()); });
page.on("pageerror", (e) => console.log("[page error]", e.message));
await page.goto(`${BASE}/player/index.html`);

const only = opt("scene") ? parseInt(opt("scene"), 10) : null;
const still = opt("still");
const sceneFiles = [];

for (let i = 0; i < sb.scenes.length; i++) {
  const n = i + 1;
  if (only && n !== only) continue;
  if (still && parseInt(still, 10) !== n) continue;
  const def = sb.scenes[i];
  const audio = narrate(def.narration);
  const lastAnim = Math.max(0, ...(def.anim || []).filter((a) => !["bob", "spin", "pulse", "flow"].includes(a.fx))
    .map((a) => (typeof a.t === "number" ? a.t : 0) + (a.dur ?? 0.6)));
  const D = Math.max(LEAD + audio.dur + TAIL, lastAnim + 0.8, def.minDuration || 0);
  console.log(`scene ${n}: narration ${audio.dur.toFixed(1)}s -> scene ${D.toFixed(1)}s`);

  await page.evaluate(([d, dur]) => window.loadScene(d, dur), [def, D]);

  if (still) {
    const t = parseFloat(still.split(":")[1]);
    await page.evaluate((tt) => window.seek(tt), t);
    await page.screenshot({ path: path.join(ROOT, "out", "still.png") });
    console.log("wrote out/still.png");
    break;
  }

  const outFile = path.join(ROOT, "out", `.${name}.scene${n}.mp4`);
  const enc = startEncoder(outFile, D, audio);
  const frames = Math.round(D * FPS);
  for (let f = 0; f < frames; f++) {
    await page.evaluate((t) => window.seek(t), f / FPS);
    const png = await page.screenshot({ type: "png" });
    if (!enc.stdin.write(png)) await new Promise((r) => enc.stdin.once("drain", r));
    if (f % FPS === 0) process.stdout.write(`\r  frame ${f}/${frames}`);
  }
  enc.stdin.end();
  await enc.done;
  process.stdout.write(`\r  ${frames} frames done        \n`);
  sceneFiles.push(outFile);
}
await browser.close();
server.close();

if (!still && sceneFiles.length) {
  const finalFile = path.join(ROOT, "out", only ? `${name}.scene${only}.mp4` : `${name}.mp4`);
  const list = path.join(ROOT, "cache", `${name}.concat.txt`);
  writeFileSync(list, sceneFiles.map((f) => `file '${f}'`).join("\n"));
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", finalFile]);
  console.log("wrote", path.relative(process.cwd(), finalFile));
}
