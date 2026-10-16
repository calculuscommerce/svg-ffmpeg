#!/usr/bin/env node
// Render a resolved spec to MP4.
//   node renderer/render.mjs spec.json out.mp4
//
// spec = {
//   fps, scale (1 = 720p, 1.5 = 1080p), concurrency,
//   captions: "path.srt" | null,          // burned in if given
//   scenes: [{ id, svgText, anim, camera, audio: "path.mp3" | null, duration, thumb: "path.png" }]
// }
// Progress is reported as JSON lines on stdout: {"event":"frame","scene":i,"frame":f,"frames":n} etc.

import { chromium } from "playwright";
import { spawn, execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [specPath, outFile] = process.argv.slice(2);
if (!specPath || !outFile) { console.error("usage: render.mjs spec.json out.mp4"); process.exit(1); }
const spec = JSON.parse(readFileSync(specPath, "utf8"));
const FPS = spec.fps || 24;
const SCALE = spec.scale || 1;
const LEAD = spec.lead ?? 0.5;
const FADE = 0.25;
const workDir = path.join(path.dirname(path.resolve(outFile)), ".render");
mkdirSync(workDir, { recursive: true });
const log = (o) => process.stdout.write(JSON.stringify(o) + "\n");

// static server (fetch() is blocked on file://)
const MIME = { ".html": "text/html", ".js": "text/javascript", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".json": "application/json", ".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg" };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (!f.startsWith(ROOT) || !existsSync(f)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": MIME[path.extname(f)] || "application/octet-stream" });
  res.end(readFileSync(f));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

function startEncoder(file, D, audio) {
  const a = ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-"];
  if (audio) a.push("-i", audio); else a.push("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono");
  a.push(
    "-filter_complex",
    `[0:v]fade=t=in:st=0:d=${FADE}:color=white,fade=t=out:st=${(D - FADE).toFixed(3)}:d=${FADE}:color=white,format=yuv420p[v];` +
    `[1:a]adelay=${Math.round(LEAD * 1000)}:all=1,apad=whole_dur=${D.toFixed(3)},afade=t=out:st=${(D - 0.2).toFixed(3)}:d=0.2[a]`,
    "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", String(FPS),
    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-t", D.toFixed(3), file,
  );
  const p = spawn("ffmpeg", a, { stdio: ["pipe", "inherit", "inherit"] });
  const done = new Promise((res, rej) => p.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))));
  return { stdin: p.stdin, done };
}

const browser = await chromium.launch();
async function newPage() {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: SCALE });
  page.on("console", (m) => { if (["warning", "error"].includes(m.type())) log({ event: "page", text: m.text() }); });
  page.on("pageerror", (e) => log({ event: "pageerror", text: e.message }));
  await page.goto(`${BASE}/player/index.html`);
  return page;
}

async function renderScene(page, sc, i) {
  const D = sc.duration;
  await page.evaluate(([d, dur]) => window.loadScene(d, dur), [{ svgText: sc.svgText, anim: sc.anim, camera: sc.camera, safeBottom: spec.captions ? 84 : 0, hand: !!sc.hand, mono: !!sc.mono, theme: sc.theme || spec.theme || null }, D]);
  if (sc.thumb) {
    await page.evaluate((t) => window.seek(t), Math.min(D * 0.75, D - 0.3));
    await page.screenshot({ path: sc.thumb, type: "png" });
  }
  const file = path.join(workDir, `scene${String(i).padStart(3, "0")}.mp4`);
  const enc = startEncoder(file, D, sc.audio || null);
  const frames = Math.round(D * FPS);
  for (let f = 0; f < frames; f++) {
    await page.evaluate((t) => window.seek(t), f / FPS);
    const png = await page.screenshot({ type: "png" });
    if (!enc.stdin.write(png)) await new Promise((r) => enc.stdin.once("drain", r));
    if (f % 12 === 0) log({ event: "frame", scene: i, frame: f, frames });
  }
  enc.stdin.end();
  await enc.done;
  log({ event: "scene_done", scene: i, frames });
  return file;
}

if (spec.stills) {
  // debug mode: one PNG per scene at the given time, no video
  const page = await newPage();
  for (const [i, sc] of spec.scenes.entries()) {
    await page.evaluate(([d, dur]) => window.loadScene(d, dur), [{ svgText: sc.svgText, anim: sc.anim, camera: sc.camera, hand: !!sc.hand, mono: !!sc.mono, theme: sc.theme || spec.theme || null }, sc.duration]);
    await page.evaluate((t) => window.seek(t), sc.stillAt ?? sc.duration - 0.3);
    await page.screenshot({ path: sc.thumb, type: "png" });
    log({ event: "still", scene: i, file: sc.thumb });
  }
  await browser.close(); server.close(); process.exit(0);
}

const files = new Array(spec.scenes.length);
let next = 0;
const workers = Math.max(1, Math.min(spec.concurrency || 3, spec.scenes.length));
await Promise.all(Array.from({ length: workers }, async () => {
  const page = await newPage();
  while (next < spec.scenes.length) {
    const i = next++;
    files[i] = await renderScene(page, spec.scenes[i], i);
  }
  await page.close();
}));
await browser.close();
server.close();

const list = path.join(workDir, "concat.txt");
writeFileSync(list, files.map((f) => `file '${f}'`).join("\n"));
if (spec.captions) {
  const style = "FontName=Patrick Hand,FontSize=20,PrimaryColour=&H00222222,OutlineColour=&H00FFFFFF,BorderStyle=1,Outline=2,Shadow=0,MarginV=22";
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list,
    "-vf", `subtitles=${spec.captions.replace(/[:\\']/g, "\\$&")}:fontsdir=${path.join(ROOT, "fonts")}:force_style='${style}'`,
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", "-movflags", "+faststart", outFile]);
} else {
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", outFile]);
}
log({ event: "done", file: outFile });
