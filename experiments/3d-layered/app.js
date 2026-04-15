import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Delaunay } from 'https://cdn.jsdelivr.net/npm/d3-delaunay@6/+esm';

// ---------- load ----------
const graph = await fetch('graph.json').then(r => r.json());
const { nodes, edges, max_depth, peaks: peakList } = graph;
const peakSet = new Set(peakList);

const callees = new Map(nodes.map(n => [n.id, []]));
const callers = new Map(nodes.map(n => [n.id, []]));
for (const e of edges) {
  callees.get(e.from)?.push(e.to);
  callers.get(e.to)?.push(e.from);
}

// ---------- state ----------
const state = {
  layout: 'fan', // 'fan' | 'umap'
};

// ---------- scene ----------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a2230);
scene.fog = new THREE.Fog(0x3a3f48, 55, 160);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 700);

// Cross-browser WebGL renderer with a fallback ladder.
// Chrome occasionally refuses to create a WebGL context with antialiasing even
// though Firefox on the same machine succeeds. We probe 4 combinations and
// take the first one that works. Each step manually creates the GL context,
// then hands it to THREE.WebGLRenderer via the `context` parameter — this is
// the only way to both (a) retry, and (b) force a specific WebGL version.
function createRenderer() {
  const canvas = document.createElement('canvas');
  const attempts = [
    { version: 'webgl2', attrs: { antialias: true,  powerPreference: 'default', failIfMajorPerformanceCaveat: false } },
    { version: 'webgl2', attrs: { antialias: false, powerPreference: 'default', failIfMajorPerformanceCaveat: false } },
    { version: 'webgl',  attrs: { antialias: true,  powerPreference: 'default', failIfMajorPerformanceCaveat: false } },
    { version: 'webgl',  attrs: { antialias: false, powerPreference: 'default', failIfMajorPerformanceCaveat: false } },
  ];
  const errors = [];
  for (const { version, attrs } of attempts) {
    try {
      const gl = canvas.getContext(version, attrs);
      if (!gl) {
        errors.push(`${version} aa=${attrs.antialias}: getContext returned null`);
        continue;
      }
      const r = new THREE.WebGLRenderer({ canvas, context: gl, ...attrs });
      // Success. Log diagnostic so future bug reports include GPU info.
      const info = gl.getExtension('WEBGL_debug_renderer_info');
      const vendor = info ? gl.getParameter(info.UNMASKED_VENDOR_WEBGL) : 'unknown';
      const rendererName = info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : 'unknown';
      console.log(`WebGL mode: ${version} · antialias: ${attrs.antialias} · vendor: ${vendor} · renderer: ${rendererName}`);
      return r;
    } catch (err) {
      errors.push(`${version} aa=${attrs.antialias}: ${err.message || err}`);
    }
  }
  // All four failed — return null so the caller can fall back to Canvas2D.
  console.warn('WebGL unavailable; falling back to Canvas2D 2D view. Reasons:\n' + errors.join('\n'));
  return null;
}

let renderer = createRenderer();
let contextLost = false;
let webglOK = renderer !== null;

if (!webglOK) {
  // Canvas2D fallback — runs on ANY browser, no WebGL required. 2D top-down
  // view of the graph: terrain triangles colored by height, nodes, edges, hover tooltips.
  render2D();
  // Stop the three.js setup dead. The 2D view is now running.
  throw new Error('[info] Using 2D Canvas fallback; three.js code skipped');
}

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);
renderer.domElement.addEventListener('webglcontextlost', (ev) => {
  ev.preventDefault();
  contextLost = true;
  console.warn('WebGL context lost — pausing render. Will auto-recover if restored.');
});
renderer.domElement.addEventListener('webglcontextrestored', () => {
  console.log('WebGL context restored — rebuilding scene.');
  contextLost = false;
  try { rebuild(); } catch (err) { console.error('rebuild after restore failed:', err); }
});

// ---------- Canvas2D fallback view ----------
function render2D() {
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:fixed;inset:0;display:block;';
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');

  // Banner at top explaining what mode we're in
  const topBanner = document.createElement('div');
  topBanner.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);background:rgba(23,27,34,.95);color:#ffb454;border:1px solid #3a3530;border-radius:6px;padding:6px 12px;font-size:12px;font-family:sans-serif;z-index:10;';
  topBanner.textContent = 'WebGL unavailable — showing 2D top-down view';
  document.body.appendChild(topBanner);

  // Tooltip element
  const tip = document.createElement('div');
  tip.style.cssText = 'position:fixed;pointer-events:none;background:rgba(23,27,34,.95);border:1px solid #262c36;border-radius:6px;padding:8px 12px;font-size:13px;color:#e6e8ec;font-family:sans-serif;max-width:340px;display:none;z-index:20;backdrop-filter:blur(6px);';
  document.body.appendChild(tip);

  // Layout: flip y so the peak (y_fan ≈ 0 in polar layout) sits at the TOP of
  // the screen and the outward fan spreads downward — matches the user's
  // "peak at top, slopes descend" mental model.
  const pts = nodes.map(n => ({ id: n.id, x: n.x_fan, y: -n.y_fan, n }));
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const spanX = xMax - xMin || 1;
  const spanY = yMax - yMin || 1;
  const pad = 60;

  let fitScale, fitOx, fitOy;
  function recomputeFit() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const scale = Math.min((canvas.width - pad * 2) / spanX, (canvas.height - pad * 2) / spanY);
    fitScale = scale;
    fitOx = canvas.width / 2 - ((xMin + xMax) / 2) * scale;
    fitOy = canvas.height / 2 - ((yMin + yMax) / 2) * scale;
  }
  function toScreen(x, y) {
    return [x * fitScale + fitOx, y * fitScale + fitOy];
  }
  recomputeFit();

  // Delaunay triangulation in 2D for terrain, skipping orphans
  const active = pts.filter(p => !p.n.is_orphan);
  const d = Delaunay.from(active.map(p => [p.x, p.y]));
  const tri = d.triangles;

  // Height colormap — same terrain palette, driven by n.height
  const heights = active.map(p => p.n.height || 0);
  const hMin = Math.min(...heights), hMax = Math.max(...heights);
  const hRange = (hMax - hMin) || 1;
  function heightColor(h) {
    const t = (h - hMin) / hRange;
    const stops = [
      [0.00, [58, 78, 90]],   // deep low = desaturated blue
      [0.30, [74, 110, 72]],  // forest
      [0.55, [154, 162, 89]], // meadow
      [0.75, [176, 154, 100]],// scree
      [0.90, [158, 146, 130]],// rock
      [1.00, [240, 236, 228]],// snow
    ];
    for (let i = 1; i < stops.length; i++) {
      if (t <= stops[i][0]) {
        const [a, ca] = stops[i - 1];
        const [b, cb] = stops[i];
        const u = (t - a) / (b - a);
        return [
          Math.round(ca[0] + (cb[0] - ca[0]) * u),
          Math.round(ca[1] + (cb[1] - ca[1]) * u),
          Math.round(ca[2] + (cb[2] - ca[2]) * u),
        ];
      }
    }
    return stops[stops.length - 1][1];
  }

  // File color for nodes (same hashing as 3D view)
  const FILE_COLORS = {};
  function fileColor(file) {
    if (FILE_COLORS[file]) return FILE_COLORS[file];
    const hue = (Object.keys(FILE_COLORS).length * 137.5) % 360;
    FILE_COLORS[file] = `hsl(${hue | 0}, 70%, 65%)`;
    return FILE_COLORS[file];
  }

  function draw(hoverId) {
    recomputeFit();
    ctx.fillStyle = '#1a2230';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Terrain triangles
    for (let i = 0; i < tri.length; i += 3) {
      const a = active[tri[i]], b = active[tri[i + 1]], c = active[tri[i + 2]];
      const [ax, ay] = toScreen(a.x, a.y);
      const [bx, by] = toScreen(b.x, b.y);
      const [cx, cy] = toScreen(c.x, c.y);
      const avgH = ((a.n.height || 0) + (b.n.height || 0) + (c.n.height || 0)) / 3;
      const [r, g, bl] = heightColor(avgH);
      ctx.fillStyle = `rgb(${r},${g},${bl})`;
      ctx.beginPath();
      ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.lineTo(cx, cy); ctx.closePath();
      ctx.fill();
    }

    // Edges
    const up = new Set(), down = new Set();
    if (hoverId) {
      const queue = [hoverId];
      while (queue.length) {
        const q = queue.shift();
        for (const e of edges) {
          if (e.to === q && !up.has(e.from)) { up.add(e.from); queue.push(e.from); }
        }
      }
      const q2 = [hoverId];
      while (q2.length) {
        const q = q2.shift();
        for (const e of edges) {
          if (e.from === q && !down.has(e.to)) { down.add(e.to); q2.push(e.to); }
        }
      }
    }
    for (const e of edges) {
      const na = pts.find(p => p.id === e.from);
      const nb = pts.find(p => p.id === e.to);
      if (!na || !nb) continue;
      const [ax, ay] = toScreen(na.x, na.y);
      const [bx, by] = toScreen(nb.x, nb.y);
      let color = e.is_primary ? 'rgba(58,68,80,.7)' : 'rgba(128,144,162,.5)';
      let width = e.is_primary ? 1.4 : 1.0;
      if (hoverId) {
        const endsTouch = e.from === hoverId || e.to === hoverId;
        const inUp = up.has(e.from) && (up.has(e.to) || e.to === hoverId);
        const inDown = (down.has(e.to) || e.to === hoverId) && (down.has(e.from) || e.from === hoverId);
        if (endsTouch && (e.to === hoverId || up.has(e.from))) { color = 'rgba(125,209,129,.95)'; width = 2.2; }
        else if (endsTouch && (e.from === hoverId || down.has(e.to))) { color = 'rgba(255,180,84,.95)'; width = 2.2; }
        else if (inUp) { color = 'rgba(125,209,129,.6)'; }
        else if (inDown) { color = 'rgba(255,180,84,.6)'; }
        else { color = 'rgba(40,46,55,.3)'; }
      }
      ctx.strokeStyle = color; ctx.lineWidth = width;
      if (e.is_primary) {
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
      } else {
        // Arc for cross-edges: quadratic curve with midpoint offset perpendicular
        const mx = (ax + bx) / 2, my = (ay + by) / 2;
        const dx = bx - ax, dy = by - ay;
        const len = Math.hypot(dx, dy) || 1;
        const nx = -dy / len, ny = dx / len;
        const arc = Math.min(40, len * 0.2);
        const cxm = mx + nx * arc, cym = my + ny * arc;
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.quadraticCurveTo(cxm, cym, bx, by); ctx.stroke();
      }
    }

    // Nodes
    for (const p of pts) {
      const [sx, sy] = toScreen(p.x, p.y);
      const isPeak = peakSet.has(p.id);
      const isOrph = !!p.n.is_orphan;
      let r = isPeak ? 9 : (isOrph ? 3 : 5 + Math.min(4, (p.n.n_callees || 0) * 0.4));
      let fill = isOrph ? 'rgba(85,92,102,.5)' : fileColor(p.n.file);
      let stroke = '#0f1216';
      if (hoverId) {
        if (p.id === hoverId) { fill = '#4c9aff'; stroke = '#fff'; r += 2; }
        else if (up.has(p.id)) { fill = '#7dd181'; }
        else if (down.has(p.id)) { fill = '#ffb454'; }
        else { fill = 'rgba(60,68,80,.5)'; }
      }
      ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    }

    // Peak label
    for (const p of pts) {
      if (peakSet.has(p.id)) {
        const [sx, sy] = toScreen(p.x, p.y);
        ctx.fillStyle = '#e6e8ec';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText((p.n.displayName || p.id), sx, sy - 14);
      }
    }
  }

  draw();

  // Hover detection
  let hoverId = null;
  canvas.addEventListener('mousemove', (e) => {
    const r = canvas.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    let closest = null, closestDist = Infinity;
    for (const p of pts) {
      const [sx, sy] = toScreen(p.x, p.y);
      const d = Math.hypot(mx - sx, my - sy);
      const radius = peakSet.has(p.id) ? 11 : 7;
      if (d < radius && d < closestDist) { closestDist = d; closest = p; }
    }
    const newId = closest ? closest.id : null;
    if (newId !== hoverId) {
      hoverId = newId;
      draw(hoverId);
    }
    if (closest) {
      tip.style.display = 'block';
      tip.style.left = Math.min(e.clientX + 12, window.innerWidth - 360) + 'px';
      tip.style.top = (e.clientY + 12) + 'px';
      const n = closest.n;
      tip.innerHTML = `<div style="font-weight:600;color:#4c9aff;margin-bottom:4px">${n.displayName || n.label || n.id}</div><div style="font-size:11px;color:#8b93a1;margin-bottom:6px">${n.qname} · ${n.file} · depth ${n.depth}</div><div style="line-height:1.5">${n.description || ''}</div>`;
    } else {
      tip.style.display = 'none';
    }
  });
  canvas.addEventListener('mouseleave', () => { tip.style.display = 'none'; hoverId = null; draw(null); });

  window.addEventListener('resize', () => draw(hoverId));

  console.log(`[2D fallback] rendered ${pts.length} nodes, ${edges.length} edges`);
}

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minPolarAngle = 0.05;
controls.maxPolarAngle = Math.PI * 0.48;

// Deeper ambient + warmer key + cooler fill = sharper contrast between lit
// and shaded slopes, more "alpine" feel.
scene.add(new THREE.AmbientLight(0xffffff, 0.30));
const sun = new THREE.DirectionalLight(0xfff3d8, 1.15);
sun.position.set(20, 50, 20);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x7aa5ff, 0.18);
fill.position.set(-25, 20, -20);
scene.add(fill);

// No separate ground plane — the terrain mesh extends far enough via its
// outermost grounding arc to cover the whole visible ground. One mesh = no seam.

// ---------- derived geometry containers (rebuilt on state change) ----------
let terrainMesh = null;
let wireMesh = null;
const nodeMeshes = [];
const nodeById = new Map();
const edgeLines = [];
let edgeByPair = new Map();
let currentPositions = new Map();
let currentHeights = new Map();

// ---------- helpers ----------
const DEPTH_H = 10;
const LIFT = 0.28;

function xyFor(n) {
  return state.layout === 'fan' ? [n.x_fan, n.y_fan] : [n.x_umap, n.y_umap];
}

function normalizedXY() {
  const raws = nodes.map(xyFor);
  const xs = raws.map(p => p[0]);
  const ys = raws.map(p => p[1]);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const span = Math.max(xMax - xMin, yMax - yMin) || 1;
  const SPREAD = 50;
  return nodes.map((_n, i) => {
    const [x, y] = raws[i];
    return [
      ((x - xMin) / span - 0.5) * SPREAD,
      ((y - yMin) / span - 0.5) * SPREAD,
    ];
  });
}

function computeHeights() {
  // In ski-slope layout the height is computed by Python (relative-descent rule).
  // For the pure-embedding layout we fall back to a simple depth-based height.
  const h = new Map();
  if (state.layout === 'fan') {
    for (const n of nodes) h.set(n.id, n.height);
  } else {
    for (const n of nodes) {
      h.set(n.id, ((max_depth - n.depth) / Math.max(1, max_depth)) * DEPTH_H);
    }
  }
  return h;
}

// Alpine palette — greens are deliberately narrow; rock/scree dominate the mid.
const TERRAIN_STOPS = [
  [0.00, new THREE.Color(0x233e49)], // deep water
  [0.06, new THREE.Color(0x2e5b4e)], // shoreline
  [0.14, new THREE.Color(0x3a6e3e)], // dark forest
  [0.22, new THREE.Color(0x5f8a48)], // forest
  [0.30, new THREE.Color(0x99a259)], // meadow (narrow)
  [0.40, new THREE.Color(0xb09a64)], // dry tundra
  [0.52, new THREE.Color(0x9a7f62)], // scree
  [0.66, new THREE.Color(0x7a6759)], // rock
  [0.80, new THREE.Color(0xa89b8d)], // upper rock
  [0.90, new THREE.Color(0xdad4c6)], // alpine / old snow
  [1.00, new THREE.Color(0xf8f5ef)], // summit
];
// Rock tiers: bare → dark (near-cliff) → shadow
const ROCK = new THREE.Color(0x6a5c4f);
const ROCK_DARK = new THREE.Color(0x3a3530);

// Sharpens u: plateau near 0, plateau near 1, narrow transition in the middle.
// Produces distinct zones with visible boundaries instead of a continuous gradient.
function sharpen(u) {
  return u < 0.5
    ? 0.5 * Math.pow(2 * u, 5)
    : 1 - 0.5 * Math.pow(2 * (1 - u), 5);
}

function terrainColor(t) {
  const stops = TERRAIN_STOPS;
  if (t <= stops[0][0]) return stops[0][1].clone();
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      const [a, ca] = stops[i - 1];
      const [b, cb] = stops[i];
      const u = sharpen((t - a) / (b - a));
      return ca.clone().lerp(cb, u);
    }
  }
  return stops[stops.length - 1][1].clone();
}

// deterministic per-vertex pseudo-random for subtle texture variation
function hash(i) {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

const FILE_COLORS = {};
function fileColor(file) {
  if (FILE_COLORS[file]) return FILE_COLORS[file];
  const hue = (Object.keys(FILE_COLORS).length * 137.5) % 360;
  FILE_COLORS[file] = new THREE.Color(`hsl(${hue | 0}, 70%, 65%)`);
  return FILE_COLORS[file];
}

// ---------- build/rebuild the whole scene ----------
function rebuild() {
  // Clear existing
  if (terrainMesh) { scene.remove(terrainMesh); terrainMesh.geometry.dispose(); terrainMesh.material.dispose(); }
  if (wireMesh) { scene.remove(wireMesh); wireMesh.material.dispose(); }
  for (const m of nodeMeshes) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
  nodeMeshes.length = 0; nodeById.clear();
  for (const l of edgeLines) { scene.remove(l); l.geometry.dispose(); l.material.dispose(); }
  edgeLines.length = 0; edgeByPair = new Map();

  const xy = normalizedXY();
  const heights = computeHeights();
  const hMax = Math.max(...[...heights.values()]);
  const hMin = Math.min(...[...heights.values()]);
  const hRange = (hMax - hMin) || 1;

  // Positions (x, y=height, z)
  currentPositions.clear();
  currentHeights.clear();
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const h = heights.get(n.id);
    currentPositions.set(n.id, [xy[i][0], h, xy[i][1]]);
    currentHeights.set(n.id, h);
  }

  // --- Terrain mesh --- (orphans excluded — they don't belong to the mountain).
  // To prevent triangle faces from bulging above straight edges (which would
  // create a misleading visual ridge), we inject Steiner points at the 1/3 and
  // 2/3 marks of every primary edge. Delaunay includes these as vertices, so
  // the mesh is forced to conform to the edge paths rather than crossing over
  // them.
  const terrainNodes = nodes.filter(n => !n.is_orphan);
  const orphanIds = new Set(nodes.filter(n => n.is_orphan).map(n => n.id));

  const steinerPositions = [];  // [x, y, z] triples
  for (const e of edges) {
    if (!e.is_primary) continue;
    if (orphanIds.has(e.from) || orphanIds.has(e.to)) continue;
    const a = currentPositions.get(e.from);
    const b = currentPositions.get(e.to);
    if (!a || !b) continue;
    for (const t of [1 / 3, 2 / 3]) {
      steinerPositions.push([
        a[0] * (1 - t) + b[0] * t,
        a[1] * (1 - t) + b[1] * t,
        a[2] * (1 - t) + b[2] * t,
      ]);
    }
  }

  // --- Grounding points ---
  // Connect the mountain to the surrounding ground with a skirt of points at
  // ground level. Each primary-tree leaf gets a "foot" projected outward, and
  // we add a rim of evenly-spaced ground points covering the mountain's arc so
  // the outer slope drapes down cleanly to the ground disc.
  const hasPrimaryChild = new Set();
  for (const e of edges) {
    if (e.is_primary) hasPrimaryChild.add(e.from);
  }
  // Ground level aligned EXACTLY with the disc (set below via groundMesh.position.y)
  // so the outermost skirt arc is coplanar with it — no visible seam.
  const groundY = hMin - 0.3;
  const groundingPositions = [];

  // Continuous skirt: three densely-populated arcs at progressively larger radii
  // and progressively lower heights. With jitter applied per-vertex for a less
  // "cookie-cutter" rim.
  let maxR = 0;
  for (const n of terrainNodes) {
    const [x, , z] = currentPositions.get(n.id);
    maxR = Math.max(maxR, Math.hypot(x, z));
  }
  const rimStart = -Math.PI - 0.25;
  const rimEnd = 0.25;
  const arcPoints = 42;
  // Arcs:
  //   inner — just past the furthest leaves, half-height (start of the drop)
  //   middle — further out, near ground
  //   outer — far enough to OVERLAP the shrunk ground disc (GROUND_RADIUS=70)
  // All grounding arcs are at true ground Y — Delaunay forms the slope from
  // leaves directly to ground with no intermediate lip/ridge.
  const arcs = [
    { r: maxR + 1.5,  h: groundY, yJitter: 0.22 },
    { r: maxR + 4.0,  h: groundY, yJitter: 0.18 },
    { r: maxR + 9.0,  h: groundY, yJitter: 0.15 },
    { r: maxR + 20.0, h: groundY, yJitter: 0.12 },
    { r: maxR + 45.0, h: groundY, yJitter: 0.06 },
    { r: maxR + 80.0, h: groundY, yJitter: 0.0  },
  ];
  let gIdx = 0;
  for (const { r: rad, h, yJitter } of arcs) {
    for (let i = 0; i <= arcPoints; i++) {
      const theta = rimStart + (rimEnd - rimStart) * (i / arcPoints);
      const rNoise = (hash(gIdx * 13 + 7) - 0.5) * 0.12; // ±6% radial jitter
      const yNoise = (hash(gIdx * 31 + 3) - 0.5) * yJitter * 2;
      const rAdj = rad * (1 + rNoise);
      groundingPositions.push([rAdj * Math.cos(theta), h + yNoise, rAdj * Math.sin(theta)]);
      gIdx++;
    }
  }

  const nNode = terrainNodes.length;
  const nSteiner = steinerPositions.length;
  const nGround = groundingPositions.length;
  const nTotal = nNode + nSteiner + nGround;

  const pts2d = [];
  for (const n of terrainNodes) {
    const [x, , z] = currentPositions.get(n.id);
    pts2d.push([x, z]);
  }
  for (const p of steinerPositions) {
    pts2d.push([p[0], p[2]]);
  }
  for (const p of groundingPositions) {
    pts2d.push([p[0], p[2]]);
  }

  // Pass 1 Delaunay — coarse triangulation used to locate centroids
  let delaunay = Delaunay.from(pts2d);
  let triangles = delaunay.triangles;

  // Build a parallel 3D array so we can look up each 2D point's full position
  const positions3D = new Array(nTotal);
  for (let i = 0; i < nNode; i++) {
    const [x, y, z] = currentPositions.get(terrainNodes[i].id);
    positions3D[i] = [x, y, z];
  }
  for (let i = 0; i < nSteiner; i++) {
    positions3D[nNode + i] = steinerPositions[i];
  }
  for (let i = 0; i < nGround; i++) {
    positions3D[nNode + nSteiner + i] = groundingPositions[i];
  }

  // Centroid subdivision: add each triangle's 3D centroid as a new vertex.
  // This roughly 4× the triangle count on pass 2, smoothing the mountain body.
  for (let t = 0; t < triangles.length; t += 3) {
    const a = positions3D[triangles[t]];
    const b = positions3D[triangles[t + 1]];
    const c = positions3D[triangles[t + 2]];
    const cx = (a[0] + b[0] + c[0]) / 3;
    const cy = (a[1] + b[1] + c[1]) / 3;
    const cz = (a[2] + b[2] + c[2]) / 3;
    pts2d.push([cx, cz]);
    positions3D.push([cx, cy, cz]);
  }

  // Pass 2 Delaunay on the augmented point set
  delaunay = Delaunay.from(pts2d);
  triangles = delaunay.triangles;

  const finalCount = positions3D.length;
  const posArr = new Float32Array(finalCount * 3);
  for (let i = 0; i < finalCount; i++) {
    const [x, y, z] = positions3D[i];
    posArr[i * 3] = x; posArr[i * 3 + 1] = y; posArr[i * 3 + 2] = z;
  }

  // Architectural ridges are baked into the heights themselves by the Python
  // build step: per-edge slope is scaled by (1 − α·min(imp_parent, imp_child)),
  // so important chains stay high longer (visible ridges) and unimportant
  // chains descend steeply (ravines). No additive JS lift needed — the terrain
  // already encodes the spine via the y-values we just read from graph.json.

  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
  geom.setIndex(Array.from(triangles));
  geom.computeVertexNormals();

  // Read computed normals and build vertex colors with slope and sun-direction awareness.
  // Steiner points pick up the same logic — they blend seamlessly with node vertices.
  const normals = geom.attributes.normal.array;
  const colArr = new Float32Array(finalCount * 3);
  // Sun direction ≈ matches our DirectionalLight ( (20, 50, 20), normalized )
  const SUN = (() => {
    const v = new THREE.Vector3(20, 50, 20).normalize();
    return { x: v.x, y: v.y, z: v.z };
  })();
  // Mountain vertices = original nodes + steiner. Everything past that is either
  // a grounding-arc vertex or a triangle-centroid subdivision point. Classify by
  // height: anything at or below hMin (the lowest mountain point) belongs to the
  // ground, regardless of how it got there.
  const nMountain = nNode + nSteiner;
  const groundThreshold = hMin; // anything at or below the lowest mountain height = ground
  for (let i = 0; i < finalCount; i++) {
    const vy = posArr[i * 3 + 1];
    if (i >= nMountain && vy <= groundThreshold) {
      // Slight darkening toward outer edge so distant ground reads as horizon fade
      const r2d = Math.hypot(posArr[i * 3], posArr[i * 3 + 2]);
      const fade = Math.min(1, Math.max(0, (r2d - 30) / 60));
      const baseGround = new THREE.Color(0x4a5a3c).lerp(new THREE.Color(0x2c3528), fade * 0.65);
      const noise = (hash(i * 11) - 0.5) * 0.06;
      colArr[i * 3] = Math.max(0, Math.min(1, baseGround.r + noise));
      colArr[i * 3 + 1] = Math.max(0, Math.min(1, baseGround.g + noise));
      colArr[i * 3 + 2] = Math.max(0, Math.min(1, baseGround.b + noise));
      continue;
    }
    const y = posArr[i * 3 + 1];
    const nx = normals[i * 3];
    const ny = normals[i * 3 + 1];
    const nz = normals[i * 3 + 2];
    // steepness: 0 = flat, 1 = vertical cliff
    const steep = Math.max(0, 1 - Math.abs(ny));
    // sun-facing dot product (−1 shadow, +1 full sun)
    const sunDot = nx * SUN.x + ny * SUN.y + nz * SUN.z;
    const shadowT = Math.max(0, Math.min(1, (0.25 - sunDot) / 0.55)); // 0 in sun, 1 in shadow

    const t = (y - hMin) / hRange;
    let mixed = terrainColor(t);

    // Tier 1 — moderate slopes bleed toward plain rock
    const rockMix = Math.min(1, Math.max(0, (steep - 0.04) * 3.0));
    mixed = mixed.clone().lerp(ROCK, rockMix * 0.72);
    // Tier 2 — genuinely steep faces (≥ ~45°) go to dark rock / cliff tone
    const cliffMix = Math.min(1, Math.max(0, (steep - 0.30) * 2.4));
    mixed.lerp(ROCK_DARK, cliffMix * 0.65);
    // Shadow tint: darken anything facing away from sun
    const shadow = new THREE.Color(0x2a2f36);
    mixed.lerp(shadow, shadowT * 0.35);

    // Per-vertex noise (subtle granular texture)
    const noise = (hash(i) - 0.5) * 0.08;
    mixed.r = Math.max(0, Math.min(1, mixed.r + noise));
    mixed.g = Math.max(0, Math.min(1, mixed.g + noise));
    mixed.b = Math.max(0, Math.min(1, mixed.b + noise));
    // Snow cap — but bare cliffs shed snow
    if (t > 0.78) {
      const snow = new THREE.Color(0xf8f5ef);
      const snowMix = (t - 0.78) / 0.22;
      mixed.lerp(snow, Math.min(1, snowMix * (1 - rockMix * 0.4 - cliffMix * 0.6)));
    }
    colArr[i * 3] = mixed.r; colArr[i * 3 + 1] = mixed.g; colArr[i * 3 + 2] = mixed.b;
  }
  geom.setAttribute('color', new THREE.BufferAttribute(colArr, 3));

  terrainMesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide,
  }));
  scene.add(terrainMesh);
  // Wireframe overlay removed — edges are drawn explicitly below so the
  // visible line network matches the actual call graph, not Delaunay triangulation.
  wireMesh = null;

  // --- Nodes ---
  const sphereGeo = new THREE.SphereGeometry(0.3, 14, 10);
  for (const n of nodes) {
    const isPeak = peakSet.has(n.id);
    const isOrphan = !!n.is_orphan;
    const base = isOrphan ? new THREE.Color(0x555c66) : fileColor(n.file).clone();
    const emissiveStrength = isOrphan ? 0.05 : (isPeak ? 0.35 : 0.15);
    const mat = new THREE.MeshStandardMaterial({
      color: base, roughness: 0.5, metalness: 0.1,
      emissive: base.clone().multiplyScalar(emissiveStrength),
      transparent: isOrphan,
      opacity: isOrphan ? 0.45 : 1.0,
    });
    const mesh = new THREE.Mesh(sphereGeo, mat);
    const [x, y, z] = currentPositions.get(n.id);
    mesh.position.set(x, y + LIFT, z);
    const s = isOrphan ? 0.7 : (isPeak ? 1.6 : 1 + Math.min(1.2, (n.n_callees || 0) * 0.1));
    mesh.scale.setScalar(s);
    mesh.userData = {
      node: n,
      baseColor: base.clone(),
      baseEmissive: base.clone().multiplyScalar(emissiveStrength),
    };
    scene.add(mesh);
    nodeMeshes.push(mesh);
    nodeById.set(n.id, mesh);
  }

  // --- Edges: primaries as straight lines (they lie on the mountain),
  // cross-edges as small arcs that visibly hop OVER the surface and any
  // edges they cross. Crossings are honest — you can see the arc going over.
  for (const e of edges) {
    const a = currentPositions.get(e.from);
    const b = currentPositions.get(e.to);
    if (!a || !b) continue;
    const isPrimary = !!e.is_primary;
    let geomPts;
    if (isPrimary) {
      geomPts = [
        new THREE.Vector3(a[0], a[1] + LIFT, a[2]),
        new THREE.Vector3(b[0], b[1] + LIFT, b[2]),
      ];
    } else {
      // Quadratic bezier arc: midpoint lifted above the higher endpoint.
      // Arc height scales with 2D distance so long crosses hop higher.
      const dx = b[0] - a[0], dz = b[2] - a[2];
      const dist2d = Math.hypot(dx, dz);
      const arcH = Math.min(4.0, 0.6 + dist2d * 0.18);
      const mid = new THREE.Vector3(
        (a[0] + b[0]) / 2,
        Math.max(a[1], b[1]) + LIFT + arcH,
        (a[2] + b[2]) / 2,
      );
      const curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(a[0], a[1] + LIFT, a[2]),
        mid,
        new THREE.Vector3(b[0], b[1] + LIFT, b[2]),
      );
      geomPts = curve.getPoints(16);
    }
    const g = new THREE.BufferGeometry().setFromPoints(geomPts);
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({
      color: isPrimary ? 0x3a4450 : 0x8090a2,
      transparent: true,
      opacity: isPrimary ? 0.55 : 0.60,
    }));
    line.userData = { edge: e, baseOpacity: isPrimary ? 0.55 : 0.60 };
    scene.add(line);
    edgeLines.push(line);
    edgeByPair.set(`${e.from}→${e.to}`, line);
  }

  // Center camera target
  const xMid = (Math.min(...xy.map(p => p[0])) + Math.max(...xy.map(p => p[0]))) / 2;
  const zMid = (Math.min(...xy.map(p => p[1])) + Math.max(...xy.map(p => p[1]))) / 2;
  const yMid = (hMin + hMax) / 2;
  controls.target.set(xMid, yMid, zMid);
  if (!camera.position.lengthSq() || initialCameraPlacement) {
    // Place the camera on the SLOPE-FACING side of the mountain.
    // The fan opens toward -Z in world space (south in the original polar
    // layout), so camera at -Z sits in front of the slope looking back at the
    // peak. Height slightly below peak gives a classic "standing at base
    // looking up" view that shows the full slope shape.
    const zSouth = Math.min(...xy.map(p => p[1]));  // most-negative world Z
    // Higher + closer in so the mountain fills the frame. With shallow ridges
    // the mountain is wider than tall; pulling the camera in makes the vertical
    // profile read more clearly against the horizon.
    camera.position.set(xMid, hMax * 1.1, zSouth - 32);
    camera.lookAt(xMid, yMid, zMid);
    initialCameraPlacement = false;
  }
}

let initialCameraPlacement = true;

// ---------- hover ----------
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let hoveredId = null;

function bfsCone(startId, adj) {
  const seen = new Set([startId]);
  const q = [startId];
  while (q.length) {
    const cur = q.shift();
    for (const n of adj.get(cur) || []) if (!seen.has(n)) { seen.add(n); q.push(n); }
  }
  return seen;
}

const UP = new THREE.Color(0x7dd181);
const DOWN = new THREE.Color(0xffb454);
const HOVER = new THREE.Color(0x4c9aff);
const DIM = new THREE.Color(0x2a3240);

const infoEl = document.getElementById('info');
const qEl = document.getElementById('i-qname');
const subEl = document.getElementById('i-sub');
const descEl = document.getElementById('i-desc');
const statsEl = document.getElementById('i-stats');
const conesEl = document.getElementById('i-cones');

function setHover(id) {
  hoveredId = id;
  if (!id) {
    for (const m of nodeMeshes) {
      m.material.color.copy(m.userData.baseColor);
      m.material.emissive.copy(m.userData.baseEmissive);
      m.material.opacity = 1; m.material.transparent = false;
    }
    for (const l of edgeLines) {
      l.material.color.setHex(0x2a3240);
      l.material.opacity = l.userData.baseOpacity;
    }
    infoEl.classList.remove('visible');
    return;
  }
  const up = bfsCone(id, callers);
  const down = bfsCone(id, callees);
  up.delete(id); down.delete(id);

  for (const m of nodeMeshes) {
    const nid = m.userData.node.id;
    let color, emit, opac;
    if (nid === id) { color = HOVER.clone(); emit = HOVER.clone().multiplyScalar(0.65); opac = 1; }
    else if (up.has(nid)) { color = UP.clone(); emit = UP.clone().multiplyScalar(0.35); opac = 1; }
    else if (down.has(nid)) { color = DOWN.clone(); emit = DOWN.clone().multiplyScalar(0.35); opac = 1; }
    else { color = DIM.clone(); emit = new THREE.Color(0); opac = 0.2; }
    m.material.color.copy(color);
    m.material.emissive.copy(emit);
    m.material.transparent = opac < 1;
    m.material.opacity = opac;
  }
  for (const l of edgeLines) {
    const { from, to } = l.userData.edge;
    const touchesHover = from === id || to === id;
    let color = 0x1a2028, opac = 0.08;
    if (touchesHover) {
      if (to === id || up.has(from)) { color = 0x7dd181; opac = 0.95; }
      if (from === id || down.has(to)) { color = 0xffb454; opac = 0.95; }
    } else if (up.has(from) && up.has(to)) { color = 0x7dd181; opac = 0.55; }
    else if (down.has(from) && down.has(to)) { color = 0xffb454; opac = 0.55; }
    l.material.color.setHex(color);
    l.material.opacity = opac;
  }

  const n = nodeById.get(id).userData.node;
  const peakTag = peakSet.has(id) ? ' · PEAK' : '';
  qEl.textContent = n.displayName || n.label || n.qname;
  subEl.textContent = `${n.qname} · ${n.file} · depth ${n.depth}${peakTag}`;
  descEl.textContent = n.description || '(no description)';
  statsEl.innerHTML = `
    <span>source lines</span><b>${n.source_lines}</b>
    <span>direct callees</span><b>${n.n_callees}</b>
    <span>direct callers</span><b>${(callers.get(id) || []).length}</b>
    <span>importance</span><b>${(n.importance || 0).toFixed(3)}</b>
    <span>semantic density</span><b>${(n.semantic_density || 0).toFixed(3)}</b>
  `;
  conesEl.innerHTML = `
    <span class="up">↑ ${up.size} caller${up.size === 1 ? '' : 's'}</span>
    <span class="down">↓ ${down.size} callee${down.size === 1 ? '' : 's'}</span>
  `;
  infoEl.classList.add('visible');
}

window.addEventListener('pointermove', (e) => {
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(nodeMeshes, false);
  if (hits.length) setHover(hits[0].object.userData.node.id);
  else if (hoveredId) setHover(null);
});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---------- control wiring ----------
for (const r of document.querySelectorAll('input[name="layout"]')) {
  r.addEventListener('change', () => { state.layout = r.value; initialCameraPlacement = true; rebuild(); });
}

rebuild();

function animate() {
  requestAnimationFrame(animate);
  if (contextLost) return;
  controls.update();
  renderer.render(scene, camera);
}
animate();

console.log(`loaded ${nodes.length} nodes, ${edges.length} edges, ${peakList.length} peaks, max_depth=${max_depth}`);
