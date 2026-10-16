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
  if (!parts) parts = await fetchSvg("../lib/parts.svg");
  sceneDur = D;
  cameraMode = def.camera || null;
  baseScale = def.safeBottom ? (720 - def.safeBottom) / 720 : 1;
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

  await document.fonts.ready;
  applyFits(scene);
  fitTexts(scene);

  for (const a of def.anim || []) {
    const els = [...scene.querySelectorAll(a.sel)];
    if (!els.length) { console.warn("no match for", a.sel); continue; }
    els.forEach((el, i) => {
      const start = resolveTime(a.t ?? 0, D) + i * (a.stagger || 0);
      const c = { el, fx: a.fx, start, dur: a.dur ?? 0.6, p: a };
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
      }
      if (a.fx === "wipe") {
        const bb = el.getBBox();
        const id = "clip" + anims.length;
        const cp = document.createElementNS(NS, "clipPath");
        cp.setAttribute("id", id);
        const r = document.createElementNS(NS, "rect");
        r.setAttribute("x", bb.x - 6); r.setAttribute("y", bb.y - 10);
        r.setAttribute("height", bb.height + 20); r.setAttribute("width", 0);
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
        for (const g of a.geoms) {
          if (q >= 1) { g.style.strokeDasharray = ""; g.style.strokeDashoffset = ""; g.style.fillOpacity = ""; continue; }
          g.style.strokeDasharray = g._len;
          g.style.strokeDashoffset = g._len * (1 - e);
          if (g._hasFill) g.style.fillOpacity = clamp((q - 0.5) / 0.5);
        }
        s.op *= p > 0 ? 1 : 0;
        break;
      }
      case "wipe": a.clipRect.setAttribute("width", (a.bb.width + 12) * easeInOut(q)); break;
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
};
