// Deterministic SVG timeline player.
//   await window.loadScene(def, duration)   def: { svg: path | svgText: string, anim: [...], camera?: "drift" }
//   window.seek(t)                           render exact state at time t (seconds). No wall-clock anywhere.
//
// Scene markup conventions
//   <g data-include="name" data-fit="W H" data-anchor="center|bottom"/>  pull a part from lib/parts.svg, scaled into W x H
//   <text data-maxw="420">                                                shrink font-size until the text fits 420px
//   Animated elements must NOT carry a transform="" attribute (CSS transform would override it) — wrap them instead.

const NS = "http://www.w3.org/2000/svg";
const scene = document.getElementById("scene");
const camera = document.getElementById("camera");
const defsHost = document.getElementById("scene-defs");
const noise = document.getElementById("wobble-noise");

let parts = null;
let anims = [];
let touched = [];
let cameraMode = null;
let sceneDur = 10;
let baseScale = 1; // < 1 leaves a free band at the bottom for burned-in captions

// ---- theme --------------------------------------------------------------------------------
let partsText = null;   // raw lib/parts.svg text; re-parsed per theme so icon ink can be recoloured
let currentTheme = null;
const FONTS = { hand: '"Hand", cursive', caveat: '"Script", "Hand", cursive', marker: '"Marker", "Hand", cursive',
  serif: '"Serif", Georgia, serif', pixel: '"Pixel", monospace', architect: '"Architect", "Hand", cursive',
  kalam: '"Kalam", "Hand", cursive', oswald: '"Oswald", "Inter", sans-serif' };
const INK_COLOURS = ["#2b2b2b", "#222222", "#222", "#111111", "#111", "#1b1b1b", "#2c3e50", "#3b2a20", "#2b1a12"];

function applyTheme(th) {
  const T = Object.assign({ bg: "#fdfcfa", ink: "#222222", primary: "#1f4aa8", accent: "#e08a1e", font_head: "hand",
    font_body: "hand", background: "plain", filter: "wobble", mono: false, stroke_scale: 1, dark: false }, th || {});
  currentTheme = T;
  document.getElementById("bg").setAttribute("fill", T.bg);
  document.body.style.background = T.bg;
  const stageEl = document.getElementById("stage");
  stageEl.style.setProperty("--font-body", FONTS[T.font_body] || FONTS.hand);
  stageEl.style.setProperty("--font-head", FONTS[T.font_head] || FONTS.hand);
  stageEl.classList.toggle("pixel", !!T.pixel);
  // background decoration
  const decor = document.getElementById("bg-decor");
  decor.replaceChildren();
  const add = (html) => { decor.insertAdjacentHTML("beforeend", html); };
  if (T.background === "paper") add('<rect width="1280" height="720" filter="url(#paper-grain)" opacity=".9"/>');
  if (T.background === "chalkboard") {
    add('<rect width="1280" height="720" filter="url(#chalk-dust)"/>');
    add('<rect x="0" y="0" width="1280" height="720" fill="none" stroke="#8a5a2b" stroke-width="26"/>');
    add('<rect x="13" y="13" width="1254" height="694" fill="none" stroke="#c89a63" stroke-width="3" opacity=".6"/>');
  }
  if (T.background === "blueprint") {
    add('<rect width="1280" height="720" fill="url(#grid-blueprint)"/>');
    add('<rect width="1280" height="720" fill="url(#grid-blueprint-big)"/>');
    add('<rect x="22" y="22" width="1236" height="676" fill="none" stroke="#ffffff" stroke-opacity=".5" stroke-width="2"/>');
  }
  if (T.background === "notebook") {
    // page edge + shadow, ruled lines below a header band, red double margin, spiral rings down the left
    add('<rect x="34" y="0" width="1246" height="720" fill="#000" opacity=".06"/>');
    add('<rect x="30" y="0" width="1250" height="720" fill="' + T.bg + '"/>');
    let rules = "";
    for (let y = 171.5; y < 720; y += 36) rules += `<path d="M30,${y} H1280" stroke="#b9cbe8" stroke-width="1.4"/>`;
    add('<g>' + rules + '</g>');
    add('<path d="M112,0 V720" stroke="#e58a8a" stroke-width="1.6"/><path d="M118,0 V720" stroke="#e58a8a" stroke-width="1.2" opacity=".7"/>');
    let rings = "";
    for (let y = 48; y < 720; y += 72) rings += `<ellipse cx="46" cy="${y}" rx="9" ry="12" fill="#e9e6dc" stroke="#9aa5b1" stroke-width="1.5"/><path d="M12,${y - 14} C8,${y - 2} 30,${y + 4} 50,${y - 6}" fill="none" stroke="#7d8793" stroke-width="5" stroke-linecap="round"/><path d="M12,${y - 14} C8,${y - 2} 30,${y + 4} 50,${y - 6}" fill="none" stroke="#c9d1da" stroke-width="2" stroke-linecap="round"/>`;
    add('<g>' + rings + '</g>');
  }
  if (T.background === "pixelgrid") add('<rect width="1280" height="720" fill="url(#grid-pixel)" opacity=".5"/>');
  if (T.frame === "whiteboard") {
    add('<rect x="10" y="10" width="1260" height="700" rx="14" fill="none" stroke="#c9ced6" stroke-width="12"/>');
    add('<rect x="16" y="16" width="1248" height="688" rx="10" fill="none" stroke="#8d949e" stroke-width="3"/>');
    add('<rect x="430" y="696" width="420" height="14" rx="4" fill="#b7bdc6" stroke="#8d949e" stroke-width="2"/>');
    add('<g><rect x="470" y="688" width="70" height="10" rx="3" fill="#1f4aa8"/><rect x="560" y="688" width="70" height="10" rx="3" fill="#d1495b"/><rect x="650" y="688" width="70" height="10" rx="3" fill="#2e8b57"/></g>');
  }
  // scene filter
  const f = T.filter === "none" ? "" : `url(#${T.filter})`;
  scene.style.filter = [f, T.mono ? "grayscale(1) contrast(1.08)" : ""].filter(Boolean).join(" ") || "none";
  // stroke weight and dark-theme icon ink
  scene.style.setProperty("--stroke-scale", T.stroke_scale);
  let txt = partsText;
  if (T.dark || T.ink.toLowerCase() !== "#222222") for (const c of INK_COLOURS) txt = txt.split(`"${c}"`).join(`"${T.ink}"`);
  if (T.dark) txt = txt.split('"#fff"').join(`"${T.bg}"`).split('"#ffffff"').join(`"${T.bg}"`);
  parts = parse(txt);
}

// ---- drawing hand -------------------------------------------------------------------------
const stage = document.getElementById("stage");
const handLayer = document.getElementById("hand");
let handMode = false;
let handImgs = undefined;         // null = use vector hands; {marker:{...}, pinch:{...}} = photo cutouts
const HAND_KIND = { draw: "marker", wipe: "marker", scalex: "marker", sketch: "marker" };
const HAND_PRE = 0;               // the marker never needs a pre-roll
const HAND_GLIDE = 0.45;          // enter / leave travel time
const HAND_OFF = { x: 1420, y: 980 };
const lerp = (a, b, k) => ({ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k });

async function loadHandAssets() {
  if (handImgs !== undefined) return;
  try {
    const r = await fetch("../assets/hands/hands.json");
    handImgs = r.ok ? await r.json() : null;
  } catch { handImgs = null; }
}

async function buildHands() {
  await loadHandAssets();
  handLayer.replaceChildren();
  const want = (currentTheme && currentTheme.hand) || "marker";
  for (const kind of ["marker"]) {
    const g = document.createElementNS(NS, "g");
    g.id = "hand-" + kind + "-g";
    const cfg = handImgs && (handImgs[want] || handImgs.marker);
    if (cfg) {
      const img = document.createElementNS(NS, "image");
      img.setAttribute("href", "../assets/hands/" + cfg.src);
      const w = cfg.width || 520;
      // place so the tip pixel lands on the origin; scale from natural width when known
      const nat = cfg.natural_width || cfg.width || 520;
      const s = w / nat;
      img.setAttribute("width", nat); img.setAttribute("height", cfg.natural_height || nat);
      img.setAttribute("transform", `scale(${s}) translate(${-cfg.tip[0]},${-cfg.tip[1]})`);
      g.appendChild(img);
      g.style.filter = "drop-shadow(10px 16px 14px rgba(0,0,0,.22))";
    } else {
      const src = parts.querySelector("#hand-" + kind);
      for (const a of src.attributes) if (a.name !== "id") g.setAttribute(a.name, a.value);
      for (const child of src.children) g.appendChild(document.importNode(child, true));
      // soft drop shadow so the hand reads as sitting above the board
      g.style.filter = "drop-shadow(6px 10px 10px rgba(0,0,0,.28))";
    }
    g.style.display = "none";
    handLayer.appendChild(g);
  }
}

function toStage(pt, ctm) {
  const p = stage.createSVGPoint(); p.x = pt.x; p.y = pt.y;
  return p.matrixTransform(ctm).matrixTransform(stage.getScreenCTM().inverse());
}

// where the hand should be for anim `a` at time t (stage coordinates)
function handTarget(a, t) {
  const q = clamp((t - a.start) / a.dur);
  const el = a.el;
  if (a.fx === "draw" && a.geoms.length) {
    const e = easeInOut(q);
    const d = e * a.totalLen;
    let acc = 0;
    for (const g of a.geoms) {
      if (d <= acc + g._len || g === a.geoms[a.geoms.length - 1]) {
        const local = Math.max(0, Math.min(g._len, d - acc));
        return toStage(g.getPointAtLength(local), g.getScreenCTM());
      }
      acc += g._len;
    }
  }
  if (a.fx === "wipe") {
    const e = easeInOut(q), n = a.lines.length;
    const i = Math.min(n - 1, Math.floor(e * n)), f = clamp(e * n - i);
    const L = a.lines[i];
    return toStage({ x: L.x - 2 + (L.width + 8) * f, y: L.y + L.height * 0.8 }, el.getScreenCTM());
  }
  if (a.fx === "sketch") {
    const e = easeInOut(q), bb = a.bb;
    const passes = Math.max(3, Math.min(12, Math.round(bb.height / 36)));
    const zig = 0.5 + 0.5 * Math.sin(e * passes * Math.PI - Math.PI / 2);
    return toStage({ x: bb.x + bb.width * zig, y: bb.y + bb.height * e }, el.getScreenCTM());
  }
  const bb = el.getBBox();
  if (a.fx === "scalex") {
    const P = a.p, v = valueAt(P, (t - a.start) / a.dur), m = P.values ? Math.max(...P.values) : Math.max(P.from ?? 0, P.to ?? 1);
    return toStage({ x: bb.x + bb.width * Math.max(v / m, 0.0001), y: bb.y + bb.height / 2 }, el.parentNode.getScreenCTM());
  }
  return toStage({ x: bb.x + bb.width / 2, y: bb.y + bb.height / 2 }, el.parentNode.getScreenCTM());
}

function updateHand(t) {
  const cands = anims.filter((a) => HAND_KIND[a.fx]).map((a) => {
    const kind = HAND_KIND[a.fx];
    const s = a.start - (kind === "pinch" ? HAND_PRE : 0);
    return { a, kind, s, e: a.start + a.dur };
  });
  let active = null, next = null, prev = null;
  for (const c of cands) {
    if (t >= c.s && t <= c.e) { if (!active || c.s > active.s) active = c; }
    else if (c.s > t) { if (!next || c.s < next.s) next = c; }
    else if (c.e < t) { if (!prev || c.e > prev.e) prev = c; }
  }
  let pos = null, kind = null, pressing = false;
  if (active) {
    kind = active.kind;
    const tt = Math.max(t, active.a.start);
    pos = handTarget(active.a, tt);
    pressing = true;
    if (kind === "pinch" && t < active.a.start) {
      // flying in with the element
      const k = easeOut((t - active.s) / HAND_PRE);
      pos = lerp(HAND_OFF, pos, k);
    }
  } else if (next && next.s - t < HAND_GLIDE && !(prev && t - prev.e < HAND_GLIDE && prev.e > next.s - HAND_GLIDE - 0.01 && false)) {
    kind = next.kind;
    const target = handTarget(next.a, next.a.start);
    const k = easeInOut(1 - (next.s - t) / HAND_GLIDE);
    pos = prev && t - prev.e < HAND_GLIDE ? lerp(handTarget(prev.a, prev.e), target, k) : lerp(HAND_OFF, target, k);
  } else if (prev && t - prev.e < HAND_GLIDE) {
    kind = prev.kind;
    pos = lerp(handTarget(prev.a, prev.e), HAND_OFF, easeInOut((t - prev.e) / HAND_GLIDE));
  }
  if (!pos) { handLayer.style.display = "none"; return; }
  handLayer.style.display = "";
  document.getElementById("hand-marker-g").style.display = "";
  const wob = Math.sin(t * 2.3) * 2.5;
  const rot = (kind === "marker" ? -6 : 2) + wob;
  const lift = pressing ? 0 : -14;
  handLayer.setAttribute("transform", `translate(${pos.x.toFixed(1)},${(pos.y + lift).toFixed(1)}) rotate(${rot.toFixed(2)})`);
}

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const easeOut = (p) => 1 - Math.pow(1 - p, 3);
const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const easeBack = (p) => { const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };

const parse = (txt) => new DOMParser().parseFromString(txt, "image/svg+xml").documentElement;
async function fetchSvg(path) { return parse(await (await fetch(path)).text()); }

function resolveTime(v, D) {
  if (typeof v === "string" && v.endsWith("%")) return (parseFloat(v) / 100) * D;
  return Number(v);
}

// Indian digit grouping: 1234567 -> 12,34,567 ; intl -> 1,234,567
function fmtNum(v, P) {
  const dec = P.decimals || 0;
  const n = Number(v.toFixed(dec));
  const [ip, fp] = Math.abs(n).toFixed(dec).split(".");
  let out;
  if (P.grouping === "none") out = ip;
  else if (P.grouping === "indian" && ip.length > 3) out = ip.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + ip.slice(-3);
  else out = ip.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return (n < 0 ? "-" : "") + (P.prefix || "") + out + (fp ? "." + fp : "") + (P.suffix || "");
}
function valueAt(P, q) {
  if (P.values) {
    const x = clamp(q) * (P.values.length - 1), i = Math.min(Math.floor(x), P.values.length - 2);
    return P.values[i] + (P.values[i + 1] - P.values[i]) * (x - i);
  }
  return (P.from ?? 0) + ((P.to ?? 1) - (P.from ?? 0)) * easeInOut(clamp(q));
}

function resolveIncludes(root) {
  root.querySelectorAll("[data-include]").forEach((ph) => {
    const name = ph.getAttribute("data-include");
    const src = parts.querySelector("#" + CSS.escape(name)) || parts.querySelector("#question");
    if (!src) throw new Error("unknown part: " + name);
    const inner = document.createElementNS(NS, "g");
    // icons inherit stroke defaults from their #icons parent group; parts keep their own presentation attrs
    const p = src.parentElement;
    if (p && p.id === "icons") for (const a of ["stroke", "stroke-width", "stroke-linejoin", "stroke-linecap", "fill"]) if (p.hasAttribute(a)) inner.setAttribute(a, p.getAttribute(a));
    for (const a of src.attributes) if (a.name !== "id" && a.name !== "transform") inner.setAttribute(a.name, a.value);
    for (const child of src.children) inner.appendChild(document.importNode(child, true));
    ph.appendChild(inner);
    ph.removeAttribute("data-include");
  });
}

function applyFits(root) {
  root.querySelectorAll("[data-fit]").forEach((g) => {
    const inner = g.firstElementChild;
    if (!inner) return;
    const [w, h] = g.getAttribute("data-fit").split(/\s+/).map(Number);
    const bb = inner.getBBox();
    if (!bb.width || !bb.height) return;
    const s = Math.min(w / bb.width, h / bb.height);
    const anchor = g.getAttribute("data-anchor") || "center";
    const cx = bb.x + bb.width / 2;
    const cy = anchor === "bottom" ? bb.y + bb.height : bb.y + bb.height / 2;
    inner.setAttribute("transform", `scale(${s}) translate(${-cx},${-cy})`);
  });
}

function fitTexts(root) {
  // every text gets an implicit max width: the canvas edge (minus a margin) for left-anchored, symmetric for middle
  root.querySelectorAll("text").forEach((t) => {
    if (t.hasAttribute("data-maxw")) return;
    const x = parseFloat(t.getAttribute("x") || 0), anchor = t.getAttribute("text-anchor") || "start";
    const ctm = t.getCTM(); const ax = ctm ? ctm.e + x * ctm.a : x;
    const maxw = anchor === "middle" ? 2 * Math.min(ax, 1280 - ax) - 16 : anchor === "end" ? ax - 20 : 1260 - ax;
    if (maxw > 40 && t.getBBox().width > maxw) t.setAttribute("data-maxw", maxw.toFixed(0));
  });
  root.querySelectorAll("text[data-maxw]").forEach((t) => {
    const maxw = Number(t.getAttribute("data-maxw"));
    let fs = parseFloat(t.getAttribute("font-size") || getComputedStyle(t).fontSize);
    for (let i = 0; i < 30 && t.getBBox().width > maxw && fs > 16; i++) {
      fs *= 0.94;
      t.setAttribute("font-size", fs.toFixed(1));
    }
  });
}

window.loadScene = async function (def, D) {
  if (!partsText) partsText = await (await fetch("../lib/parts.svg")).text();
  applyTheme(def.theme);
  sceneDur = D;
  cameraMode = def.camera || null;
  baseScale = def.safeBottom ? (720 - def.safeBottom) / 720 : 1;
  handMode = !!def.hand && (!currentTheme || currentTheme.hand !== "none");
  if (handMode) await buildHands(); else handLayer.style.display = "none";
  const svg = def.svgText ? parse(`<svg xmlns="${NS}">${def.svgText}</svg>`) : await fetchSvg("../" + def.svg);
  if (svg.nodeName === "parsererror" || svg.querySelector("parsererror")) throw new Error("scene SVG parse error: " + svg.textContent.slice(0, 200));

  scene.replaceChildren();
  defsHost.replaceChildren();
  anims = [];
  touched = [];
  camera.style.transformOrigin = baseScale < 1 ? "640px 0px" : "640px 380px";
  camera.style.transform = `scale(${baseScale})`;

  parts.querySelectorAll("[data-def]").forEach((n) => defsHost.appendChild(document.importNode(n, true)));
  resolveIncludes(svg);
  for (const child of [...svg.childNodes]) scene.appendChild(document.importNode(child, true));

  if (currentTheme && currentTheme.stroke_scale !== 1) {
    scene.querySelectorAll("[stroke-width]").forEach((el) => {
      const w = parseFloat(el.getAttribute("stroke-width"));
      if (w > 1.6) el.setAttribute("stroke-width", (w * currentTheme.stroke_scale).toFixed(2));
    });
  }
  await document.fonts.ready;
  await Promise.all([...scene.querySelectorAll("image")].map((im) => new Promise((res) => {
    const href = im.getAttribute("href");
    if (!href) return res();
    const probe = new Image();
    probe.onload = probe.onerror = () => res();
    probe.src = href;
  })));
  applyFits(scene);
  fitTexts(scene);

  for (const a of def.anim || []) {
    const els = [...scene.querySelectorAll(a.sel)];
    if (!els.length) { console.warn("no match for", a.sel); continue; }
    els.forEach((el, i) => {
      const start = resolveTime(a.t ?? 0, D) + i * (a.stagger || 0);
      const fx = handMode && ["pop", "grow", "slide", "fade"].includes(a.fx) ? "sketch" : a.fx;
      const c = { el, fx, start, dur: a.dur ?? 0.6, p: a };
      anims.push(c);
      if (!touched.includes(el)) {
        touched.push(el);
        el.style.transformBox = "fill-box";
        el.style.transformOrigin = a.origin || "center";
      } else if (a.origin) el.style.transformOrigin = a.origin;
      if (a.fx === "draw") {
        c.geoms = [...(el.matches("path,line,polyline,polygon,circle,ellipse,rect") ? [el] : []), ...el.querySelectorAll("path,line,polyline,polygon,circle,ellipse,rect")]
          .filter((g) => typeof g.getTotalLength === "function");
        c.geoms.forEach((g) => { g._len = g.getTotalLength() || 1; g._hasFill = g.getAttribute("fill") && g.getAttribute("fill") !== "none"; });
        c.totalLen = c.geoms.reduce((s, g) => s + g._len, 0) || 1;
      }
      if (fx === "wipe") {
        // one clip rect per text line so the reveal (and the hand) runs line by line
        const bb = el.getBBox();
        const spans = el.tagName === "text" ? [...el.querySelectorAll("tspan")].filter((t) => t.hasAttribute("x")) : [];
        const lines = (spans.length > 1 ? spans : [el]).map((n) => { const b = n.getBBox(); return { x: b.x, y: b.y, width: b.width, height: b.height }; });
        const id = "clip" + anims.length;
        const cp = document.createElementNS(NS, "clipPath");
        cp.setAttribute("id", id);
        c.clipRects = lines.map((L) => {
          const r = document.createElementNS(NS, "rect");
          r.setAttribute("x", L.x - 6); r.setAttribute("y", L.y - 6);
          r.setAttribute("height", L.height + 12); r.setAttribute("width", 0);
          cp.appendChild(r);
          return r;
        });
        defsHost.appendChild(cp);
        c.lines = lines; c.bb = bb;
        el.setAttribute("clip-path", `url(#${id})`);
      }
      if (fx === "sketch") {
        const bb = el.getBBox();
        const id = "clip" + anims.length;
        const cp = document.createElementNS(NS, "clipPath");
        cp.setAttribute("id", id);
        const r = document.createElementNS(NS, "rect");
        r.setAttribute("x", bb.x - 8); r.setAttribute("y", bb.y - 8);
        r.setAttribute("width", bb.width + 16); r.setAttribute("height", 0);
        cp.appendChild(r);
        defsHost.appendChild(cp);
        c.clipRect = r; c.bb = bb;
        el.setAttribute("clip-path", `url(#${id})`);
      }
    });
  }
  window.seek(0);
};

window.seek = function (t) {
  noise.setAttribute("seed", String(1 + (Math.floor(t * 8) % 7)));
  if (cameraMode === "drift") {
    const k = baseScale * (1 + 0.035 * clamp(t / sceneDur));
    camera.style.transform = `scale(${k})`;
  }

  const st = new Map();
  for (const el of touched) st.set(el, { op: 1, tx: 0, ty: 0, sx: 1, sy: 1, rot: 0 });

  for (const a of anims) {
    const s = st.get(a.el);
    const p = (t - a.start) / a.dur;
    const q = clamp(p);
    const P = a.p;
    switch (a.fx) {
      case "fade": s.op *= easeOut(q); break;
      case "fadeout": s.op *= 1 - easeInOut(q); break;
      case "pop": { const e = p <= 0 ? 0 : easeBack(q); s.sx *= e; s.sy *= e; s.op *= clamp(p * 5); break; }
      case "grow": { const e = easeOut(q); s.sy *= Math.max(e, 0.001); s.sx *= 0.6 + 0.4 * e; s.op *= clamp(p * 6); break; }
      case "slide": { const e = easeOut(q); s.tx += (P.dx || 0) * (1 - e); s.ty += (P.dy || 0) * (1 - e); s.op *= e; break; }
      case "draw": {
        const e = easeInOut(q);
        let acc = 0;
        for (const g of a.geoms) {
          if (q >= 1) { g.style.strokeDasharray = ""; g.style.strokeDashoffset = ""; g.style.fillOpacity = ""; continue; }
          // hand mode draws strokes one after another so the pen tip is well defined; otherwise all at once
          const gq = handMode ? clamp((e * a.totalLen - acc) / g._len) : e;
          acc += g._len;
          g.style.strokeDasharray = g._len;
          g.style.strokeDashoffset = g._len * (1 - gq);
          if (g._hasFill) g.style.fillOpacity = handMode ? clamp((gq - 0.6) / 0.4) : clamp((q - 0.5) / 0.5);
        }
        s.op *= p > 0 ? 1 : 0;
        break;
      }
      case "wipe": {
        const e = easeInOut(q), n = a.lines.length;
        a.clipRects.forEach((r, i) => r.setAttribute("width", (a.lines[i].width + 12) * clamp(e * n - i)));
        break;
      }
      case "sketch": a.clipRect.setAttribute("height", (a.bb.height + 16) * easeInOut(q)); s.op *= p > 0 ? 1 : 0; break;
      case "count": a.el.textContent = fmtNum(valueAt(P, p), P); s.op *= p >= 0 ? 1 : 0; break;
      case "scalex": { const v = valueAt(P, p), m = P.values ? Math.max(...P.values) : Math.max(P.from ?? 0, P.to ?? 1); s.sx *= Math.max(v / m, 0.0001); s.op *= p > 0 ? 1 : 0; break; }
      case "bob": if (t >= a.start) { const ph = Math.sin(((t - a.start) / (P.period || 2)) * 2 * Math.PI); s.tx += (P.dx || 0) * ph; s.ty += (P.dy || 6) * ph; } break;
      case "spin": if (t >= a.start) s.rot += (360 * (t - a.start)) / (P.period || 20); break;
      case "pulse": if (t >= a.start) { const k = 1 + (P.amp || 0.05) * Math.sin(((t - a.start) / (P.period || 1.5)) * 2 * Math.PI); s.sx *= k; s.sy *= k; } break;
      case "flow": if (t >= a.start) { const sp = P.speed || 40; const gs = a.el.querySelectorAll("path,line"); (gs.length ? gs : [a.el]).forEach((g) => { g.style.strokeDashoffset = String(-sp * (t - a.start)); }); } break;
    }
  }
  for (const [el, s] of st) {
    el.style.opacity = s.op;
    el.style.transform = `translate(${s.tx}px,${s.ty}px) rotate(${s.rot}deg) scale(${s.sx},${s.sy})`;
  }
  if (handMode) updateHand(t);
};
