import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { Delaunay } from 'd3-delaunay';
import cdt2d from 'cdt2d';
import { graph, snapshot, saved, initialSelection, setupSnapshotUI, setupThemes, updateURL } from './snapshot.js';

// ---------- load ----------
const { nodes, edges, max_depth, peaks: peakList } = graph;
const peakSet = new Set(peakList);

const callees = new Map(nodes.map(n => [n.id, []]));
const callers = new Map(nodes.map(n => [n.id, []]));
for (const e of edges) {
  callees.get(e.from)?.push(e.to);
  callers.get(e.to)?.push(e.from);
}

// ---------- state ----------
const requestedLayout = new URLSearchParams(location.search).get('layout');
const state = {layout: ['fan', 'umap'].includes(requestedLayout) ? requestedLayout : (saved ? 'fan' : 'umap')};
for (const radio of document.querySelectorAll('input[name="layout"]')) radio.checked = radio.value === state.layout;

// ---------- scene ----------
const scene = new THREE.Scene();
// A transparent scene lets the portfolio's chalkboard sit behind the real terrain.
const BOARD_BG = new THREE.Color(0x233b35);
scene.background = null;
scene.fog = new THREE.FogExp2(BOARD_BG.getHex(), 0.003);

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
      const gl = canvas.getContext(version, { ...attrs, alpha: true });
      if (!gl) {
        errors.push(`${version} aa=${attrs.antialias}: getContext returned null`);
        continue;
      }
      const r = new THREE.WebGLRenderer({ canvas, context: gl, alpha: true, ...attrs });
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
  const paint = render2D(selectFlat);
  document.body.dataset.renderer = 'canvas2d';
  document.body.dataset.ready = 'true';
  document.getElementById('controls').hidden = true;
  const evidence = setupSnapshotUI(selectFlat);
  function selectFlat(id) {
    const node = nodes.find(n => n.id === id);
    document.getElementById('empty-info').hidden = !!node;
    document.getElementById('selected-info').hidden = !node;
    document.getElementById('function-picker').value = node?.id || '';
    if (node) {
      document.getElementById('i-qname').textContent = node.displayName || node.label;
      document.getElementById('i-sub').textContent = `${node.file}:${node.location?.start_line || '?'} · 2D map`;
      document.getElementById('i-desc').textContent = node.description || '';
      evidence(node);
    }
    paint(node?.id);
    document.body.dataset.selectedNode = node?.id || '';
    updateURL({node: node?.id});
  }
  const picker = document.getElementById('function-picker');
  for (const node of nodes) picker.add(new Option(`${node.displayName || node.label} · ${node.file}`, node.id));
  picker.addEventListener('change', () => selectFlat(picker.value));
  document.getElementById('start-exploring').addEventListener('click', () => selectFlat(snapshot.entries?.find(id => nodes.some(n => n.id === id)) || peakList[0]));
  document.getElementById('clear-selection').addEventListener('click', () => selectFlat(null));
  selectFlat(initialSelection);
  await setupThemes(() => paint(document.body.dataset.selectedNode));
  document.getElementById('graph-count').textContent = `${nodes.length} functions · ${edges.length} calls · 2D fallback`;
  document.querySelector('#legend p').textContent = 'Point at a function to see its connections';
  // Stop the three.js setup dead. The 2D view is now running.
  throw new Error('[info] Using 2D Canvas fallback; three.js code skipped');
}

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
// Facet shading supplies depth without the cost of shadow maps.
renderer.shadowMap.enabled = false;
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
function render2D(onSelect) {
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:fixed;inset:0;display:block;';
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext('2d');

  // Banner at top explaining what mode we're in
  const topBanner = document.createElement('div');
  topBanner.className = 'paper';
  topBanner.style.cssText = 'position:fixed;top:235px;left:50%;transform:translateX(-50%);padding:6px 12px;font-size:14px;z-index:10;max-width:90vw;pointer-events:none;';
  topBanner.textContent = '2D map · color shows prominence';
  document.body.appendChild(topBanner);

  // Tooltip element
  const tip = document.createElement('div');
  tip.style.cssText = 'position:fixed;pointer-events:none;background:rgba(23,27,34,.95);border:1px solid #262c36;border-radius:6px;padding:8px 12px;font-size:13px;color:#e6e8ec;font-family:sans-serif;max-width:340px;display:none;z-index:20;backdrop-filter:blur(6px);';
  document.body.appendChild(tip);

  // Layout: flip y so the peak (y_fan ≈ 0 in polar layout) sits at the TOP of
  // the screen and the outward fan spreads downward — matches the user's
  // "peak at top, slopes descend" mental model.
  const pts = nodes.map(n => ({ id: n.id, x: state.layout === 'umap' ? n.x_umap : n.x_fan, y: -(state.layout === 'umap' ? n.y_umap : n.y_fan), n }));
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
    const left = canvas.width > 860 ? 355 : pad;
    const top = 235, bottom = canvas.height - 125;
    const scale = Math.min((canvas.width - left - pad) / spanX, (bottom - top) / spanY);
    fitScale = scale;
    fitOx = (left + canvas.width - pad) / 2 - ((xMin + xMax) / 2) * scale;
    fitOy = (top + bottom) / 2 - ((yMin + yMax) / 2) * scale;
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
  const flatHeight = n => state.layout === 'umap' ? (n.semantic_height ?? n.height) : n.height;
  const heights = active.map(p => flatHeight(p.n) || 0);
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

  let flatSelection = null;
  function draw(hoverId) {
    hoverId = flatSelection || hoverId;
    recomputeFit();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Terrain triangles
    for (let i = 0; i < tri.length; i += 3) {
      const a = active[tri[i]], b = active[tri[i + 1]], c = active[tri[i + 2]];
      const [ax, ay] = toScreen(a.x, a.y);
      const [bx, by] = toScreen(b.x, b.y);
      const [cx, cy] = toScreen(c.x, c.y);
      const avgH = ((flatHeight(a.n) || 0) + (flatHeight(b.n) || 0) + (flatHeight(c.n) || 0)) / 3;
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
      tip.textContent = `${n.displayName || n.label || n.id} · ${n.file} · ${n.description || ''}`;
    } else {
      tip.style.display = 'none';
    }
  });
  canvas.addEventListener('mouseleave', () => { tip.style.display = 'none'; hoverId = null; draw(null); });
  canvas.addEventListener('click', event => {
    const hit = pts.map(p => ({p, distance: Math.hypot(toScreen(p.x, p.y)[0] - event.clientX, toScreen(p.x, p.y)[1] - event.clientY)})).sort((a, b) => a.distance - b.distance)[0];
    if (hit?.distance < 16) onSelect(hit.p.id);
  });

  window.addEventListener('resize', () => draw(hoverId));

  console.log(`[2D fallback] rendered ${pts.length} nodes, ${edges.length} edges`);
  return id => { flatSelection = id; draw(id); };
}

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
controls.dampingFactor = 0.08;
controls.minPolarAngle = 0.05;
controls.maxPolarAngle = Math.PI * 0.48;

// Warm paper colours and stepped shading keep the terrain close to the portfolio.
scene.add(new THREE.HemisphereLight(0xfff9e9, 0x61766c, 1.6));
const rim = new THREE.DirectionalLight(0xfff3d6, 1.7);
rim.position.set(-20, 50, -20);
scene.add(rim);

// ---------- derived geometry containers (rebuilt on state change) ----------
let terrainMesh = null;
let wireMesh = null;
let peakBeacon = null;         // warm PointLight at the summit
let dustParticles = null;      // sparse drifting motes around the mountain
const nodeMeshes = [];
const nodeById = new Map();
const edgeLines = [];
let edgeByPair = new Map();
let currentPositions = new Map();
let currentHeights = new Map();

// ---------- helpers ----------
const DEPTH_H = 10;
const LIFT = 0.55;

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
  // Semantic maps use baked importance heights in the embedding projection.
  const h = new Map();
  if (state.layout === 'fan') {
    for (const n of nodes) h.set(n.id, n.height);
  } else {
    for (const n of nodes) {
      h.set(n.id, n.semantic_height ?? ((max_depth - n.depth) / Math.max(1, max_depth)) * DEPTH_H);
    }
  }
  return h;
}

// Sage, pale blue and cream borrow the portfolio's paper palette.
const TERRAIN_STOPS = [
  [0.00, new THREE.Color(0x536f65)],
  [0.25, new THREE.Color(0x91afa0)],
  [0.52, new THREE.Color(0xa4bec3)],
  [0.77, new THREE.Color(0xccc7a6)],
  [1.00, new THREE.Color(0xf5eedd)],
];
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
  const colours = [0xe8d9a5, 0xbdd4bf, 0xa8c7d1, 0xe0bda6, 0xc5bfdb, 0xe2d8c4];
  FILE_COLORS[file] = new THREE.Color(colours[Object.keys(FILE_COLORS).length % colours.length]);
  return FILE_COLORS[file];
}

// ---------- build/rebuild the whole scene ----------
function rebuild() {
  // Clear existing
  if (terrainMesh) { scene.remove(terrainMesh); terrainMesh.geometry.dispose(); terrainMesh.material.dispose(); }
  if (wireMesh) { scene.remove(wireMesh); wireMesh.geometry.dispose(); wireMesh.material.dispose(); wireMesh = null; }
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
  // Primary-tree spines are preserved as sharp polygon edges; no vertices
  // added on them. Rounding happens purely through "parallel-cut"
  // subdivision of the NON-spine edges (post-Delaunay, see below). Heights
  // on those midpoints are straight-line interpolation, so no new peaks
  // or invented altitudes.
  const terrainNodes = nodes.filter(n => !n.is_orphan);
  const steinerPositions = [];

  // --- Grounding points ---
  // Connect the mountain to the surrounding ground with a skirt of points at
  // ground level. Each primary-tree leaf gets a "foot" projected outward, and
  // we add a rim of evenly-spaced ground points covering the mountain's arc so
  // the outer slope drapes down cleanly to the ground disc.
  const hasPrimaryChild = new Set();
  for (const e of edges) {
    if (e.is_primary) hasPrimaryChild.add(e.from);
  }
  // Ground level drops below the lowest mountain node. The outermost arcs
  // sit at groundY; inner arcs are lifted closer to leaf-height so the slope
  // from leaf to ground is gradual rather than a vertical cliff — otherwise
  // leaves at the perimeter end up on a near-vertical wedge of terrain and
  // the grass behind them reads as "floating on ground" to the eye.
  const groundY = hMin - 2.5;
  const apronHigh = hMin - 0.6;  // just below the lowest leaf
  const apronMid  = hMin - 1.5;
  const groundingPositions = [];

  // Continuous skirt: three densely-populated arcs at progressively larger radii
  // and progressively lower heights. With jitter applied per-vertex for a less
  // "cookie-cutter" rim.
  let maxR = 0;
  for (const n of terrainNodes) {
    const [x, , z] = currentPositions.get(n.id);
    maxR = Math.max(maxR, Math.hypot(x, z));
  }
  // Full-circle grounding: arcs wrap all the way around the mountain so the
  // terrain mesh is continuous regardless of viewing angle.
  const rimStart = -Math.PI;
  const rimEnd = Math.PI;
  const arcPoints = 42;
  // Arcs:
  //   inner — just past the furthest leaves, half-height (start of the drop)
  //   middle — further out, near ground
  //   outer — far enough to OVERLAP the shrunk ground disc (GROUND_RADIUS=70)
  // All grounding arcs are at true ground Y — Delaunay forms the slope from
  // leaves directly to ground with no intermediate lip/ridge.
  const arcs = [
    { r: maxR + 1.2,  h: apronHigh, yJitter: 0.18 },
    { r: maxR + 3.5,  h: apronMid,  yJitter: 0.15 },
    { r: maxR + 8.0,  h: groundY,   yJitter: 0.15 },
    { r: maxR + 18.0, h: groundY,   yJitter: 0.12 },
    { r: maxR + 40.0, h: groundY,   yJitter: 0.06 },
    { r: maxR + 80.0, h: groundY,   yJitter: 0.0  },
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

  // Index mapping + primary-edge sets, built BEFORE the first triangulation
  // so we can pass primary edges as CDT constraints. idToIndex maps node id
  // to its slot in pts2d (first nNode slots are terrainNodes in order).
  // primaryKeys is the dedup'd set of primary edges used later to skip
  // subdivision on the spine. constraintEdges is the list of [ia, ib] pairs
  // that cdt2d must preserve as polygon edges.
  const idToIndex = new Map();
  for (let i = 0; i < nNode; i++) idToIndex.set(terrainNodes[i].id, i);
  const primaryKeys = new Set();
  const constraintEdges = [];
  for (const e of edges) {
    // Similarity coordinates can cross call paths in 2D. Crossing segments are
    // invalid CDT constraints, so only the call-path layout forces terrain ridges.
    // The similarity view still draws every real call as a separate graph edge.
    if (state.layout !== 'fan' || !e.is_primary || graph.constrained_spines === false) continue;
    const ia = idToIndex.get(e.from);
    const ib = idToIndex.get(e.to);
    if (ia == null || ib == null || ia === ib) continue;
    primaryKeys.add(ia < ib ? (ia * 1000003 + ib) : (ib * 1000003 + ia));
    constraintEdges.push([ia, ib]);
  }

  // Pass 1 — Constrained Delaunay Triangulation. Every primary call edge is
  // passed as a required edge, so the 2D segment between two connected
  // nodes is guaranteed to be shared between two polygons of the mesh.
  // That means the straight cyan line we draw on top of each primary edge
  // sits flush on the surface instead of clipping into a terrain bulge.
  let cdtTris = cdt2d(pts2d, constraintEdges, { exterior: true });
  let triangles = new Uint32Array(cdtTris.length * 3);
  for (let t = 0; t < cdtTris.length; t++) {
    triangles[t * 3]     = cdtTris[t][0];
    triangles[t * 3 + 1] = cdtTris[t][1];
    triangles[t * 3 + 2] = cdtTris[t][2];
  }

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

  // Parallel-cut subdivision notes and primary-edge skip logic live below.

  // Parallel-cut subdivision: for each triangle flanking a primary edge,
  // split its TWO non-spine edges at their midpoints. The new polygon
  // edge connecting those midpoints runs parallel to the spine (midsegment
  // theorem). The spine edge itself is never touched. Midpoint heights are
  // pure linear interpolation — they sit exactly on the plane of the
  // original triangle, so the surface shape is UNCHANGED, but the mesh now
  // has more triangles that can take on varying orientations after
  // re-triangulation with neighbors. Result: same geometry, more facets,
  // smoother appearance toward the spine. No new peaks. No invented
  // altitudes. No cross-branch stair artifacts.
  const SUBDIV_PASSES = 2;
  for (let pass = 0; pass < SUBDIV_PASSES; pass++) {
    const groundStart = nNode + nSteiner;
    const groundEnd = nNode + nSteiner + nGround;
    const seen = new Set();
    const before = positions3D.length;
    for (let t = 0; t < triangles.length; t += 3) {
      for (let k = 0; k < 3; k++) {
        const ia = triangles[t + k];
        const ib = triangles[t + ((k + 1) % 3)];
        if ((ia >= groundStart && ia < groundEnd) || (ib >= groundStart && ib < groundEnd)) continue;
        const key = ia < ib ? (ia * 1000003 + ib) : (ib * 1000003 + ia);
        if (seen.has(key)) continue;
        seen.add(key);
        // Skip spine edges — primary-tree edges stay as they are.
        if (pass === 0 && primaryKeys.has(key)) continue;
        const a = positions3D[ia], b = positions3D[ib];
        // Straight-line interpolation. Midpoint lies on the plane of the
        // original triangle, guaranteeing no peaks/uphills/stairs.
        pts2d.push([(a[0] + b[0]) / 2, (a[2] + b[2]) / 2]);
        positions3D.push([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2]);
      }
    }
    if (positions3D.length === before) break;
    // Re-triangulate with the SAME primary-edge constraints after midpoints
    // were added, so primary edges remain mesh edges even after subdivision.
    cdtTris = cdt2d(pts2d, constraintEdges, { exterior: true });
    triangles = new Uint32Array(cdtTris.length * 3);
    for (let t = 0; t < cdtTris.length; t++) {
      triangles[t * 3]     = cdtTris[t][0];
      triangles[t * 3 + 1] = cdtTris[t][1];
      triangles[t * 3 + 2] = cdtTris[t][2];
    }
  }

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

  // Colour by the existing height values; lighting supplies the facet shading.
  const colArr = new Float32Array(finalCount * 3);
  // Mountain vertices = original nodes + steiner. Everything past that is either
  // a grounding-arc vertex or a triangle-centroid subdivision point. Classify by
  // height: anything at or below hMin (the lowest mountain point) belongs to the
  // ground, regardless of how it got there.
  const nMountain = nNode + nSteiner;
  const groundThreshold = hMin; // anything at or below the lowest mountain height = ground
  for (let i = 0; i < finalCount; i++) {
    const vy = posArr[i * 3 + 1];
    if (i >= nMountain && vy <= groundThreshold) {
      // The apron fades into the chalkboard in the material shader below.
      const baseGround = BOARD_BG.clone();
      colArr[i * 3] = baseGround.r;
      colArr[i * 3 + 1] = baseGround.g;
      colArr[i * 3 + 2] = baseGround.b;
      continue;
    }
    const y = posArr[i * 3 + 1];
    const t = (y - hMin) / hRange;
    let mixed = terrainColor(t);
    // Tiny grain to break up dead-uniform triangles, but nothing textured.
    const fine = (hash(i * 7) - 0.5) * 0.008;
    mixed.r = Math.max(0, Math.min(1, mixed.r + fine));
    mixed.g = Math.max(0, Math.min(1, mixed.g + fine));
    mixed.b = Math.max(0, Math.min(1, mixed.b + fine));
    colArr[i * 3] = mixed.r; colArr[i * 3 + 1] = mixed.g; colArr[i * 3 + 2] = mixed.b;
  }
  geom.setAttribute('color', new THREE.BufferAttribute(colArr, 3));

  // Keep every terrain vertex and triangle. Fade only the flat grounding apron
  // into the board, so its distant horizon does not look like a second backdrop.
  function fadeApron(material) {
    material.onBeforeCompile = shader => {
      shader.uniforms.apronHeight = { value: hMin };
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', '#include <common>\nvarying float surfaceHeight;')
        .replace('#include <begin_vertex>', '#include <begin_vertex>\nsurfaceHeight = position.y;');
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\nvarying float surfaceHeight;\nuniform float apronHeight;')
        .replace('#include <clipping_planes_fragment>', '#include <clipping_planes_fragment>\nif (surfaceHeight <= apronHeight + 0.02) discard;')
        .replace('#include <opaque_fragment>', '#include <opaque_fragment>\ngl_FragColor.a *= smoothstep(apronHeight, apronHeight + 1.2, surfaceHeight);');
    };
  }
  const terrainMaterial = new THREE.MeshToonMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    fog: true,
    transparent: true,
  });
  terrainMaterial.flatShading = true;
  fadeApron(terrainMaterial);
  terrainMesh = new THREE.Mesh(geom, terrainMaterial);
  scene.add(terrainMesh);
  // Debug handle for inspection via chrome MCP.
  window.__debug = { scene, terrainMesh, camera, controls, THREE, graph, nodeById, edgeLines, currentPositions, state, selectNode: selectFunction, renderer };

  // Ink only the stronger terrain creases; call paths remain the main lines.
  const edgesGeom = new THREE.EdgesGeometry(geom, 38);
  wireMesh = new THREE.LineSegments(
    edgesGeom,
    new THREE.LineBasicMaterial({
      color: 0x24463e,
      transparent: true,
      opacity: 0.38,
      fog: true,
    }),
  );
  fadeApron(wireMesh.material);
  scene.add(wireMesh);

  // Minimal aesthetic: no peak beacon, no dust motes.
  if (peakBeacon) { scene.remove(peakBeacon); peakBeacon = null; }
  if (dustParticles) {
    scene.remove(dustParticles);
    dustParticles.geometry.dispose();
    dustParticles.material.dispose();
    dustParticles = null;
  }

  // --- Nodes ---
  const sphereGeo = new THREE.SphereGeometry(0.38, 14, 10);
  for (const n of nodes) {
    const isPeak = peakSet.has(n.id);
    const isOrphan = !!n.is_orphan;
    const base = isOrphan ? new THREE.Color(0x809889) : fileColor(n.file).clone();
    // Small paper-coloured markers retain the original file grouping and size cues.
    const emissiveStrength = 0.04;
    const mat = new THREE.MeshStandardMaterial({
      color: base,
      roughness: 0.8,
      metalness: 0.0,
      emissive: base.clone(),
      emissiveIntensity: emissiveStrength,
      transparent: isOrphan,
      opacity: isOrphan ? 0.5 : 1.0,
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
    const isPrimary = !!e.is_primary && graph.constrained_spines !== false;
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
    const g = new LineGeometry().setPositions(geomPts.flatMap(p => p.toArray()));
    // Screen-sized ink strokes stay readable as the responsive camera pulls back.
    // Depth testing preserves the original occlusion of paths behind the terrain.
    const baseOp = isPrimary ? 0.82 : 0.65;
    const baseColor = isPrimary ? 0x244b49 : 0x795538;
    const mat = new LineMaterial({
      color: baseColor, transparent: true, opacity: baseOp,
      linewidth: isPrimary ? 1.9 : 1.5,
      dashed: saved ? !isPrimary : e.confidence !== 'resolved', dashSize: 0.22, gapSize: 0.42,
      resolution: new THREE.Vector2(window.innerWidth, window.innerHeight),
    });
    const line = new Line2(g, mat);
    line.computeLineDistances();
    line.userData = { edge: e, baseOpacity: baseOp, baseColor };
    scene.add(line);
    edgeLines.push(line);
    edgeByPair.set(`${e.from}→${e.to}`, line);
  }

}

// ---------- hover ----------
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let hoveredId = null;
let pinnedId = null; // A click keeps the selected family and note visible until cleared.

function bfsCone(startId, adj) {
  const seen = new Set([startId]);
  const q = [startId];
  while (q.length) {
    const cur = q.shift();
    for (const n of adj.get(cur) || []) if (!seen.has(n)) { seen.add(n); q.push(n); }
  }
  return seen;
}

const UP = new THREE.Color(0xa9cdb4);
const DOWN = new THREE.Color(0xe7ae8a);
const HOVER = new THREE.Color(0xf0d982);
const DIM = new THREE.Color(0x667e71);

const infoEl = document.getElementById('info');
const qEl = document.getElementById('i-qname');
const subEl = document.getElementById('i-sub');
const descEl = document.getElementById('i-desc');
const statsEl = document.getElementById('i-stats');
const conesEl = document.getElementById('i-cones');

// Visual highlighting (node colors + edge colors) separated from info-panel
// updates so the panel can track hover while the highlighted family tree
// stays pinned to a clicked node.
function paintFamilyTree(id) {
  if (!id) {
    for (const m of nodeMeshes) {
      m.material.color.copy(m.userData.baseColor);
      m.material.emissive.copy(m.userData.baseEmissive);
      m.material.opacity = 1; m.material.transparent = false;
    }
    for (const l of edgeLines) {
      // Restore each edge's ink colour and opacity at rest.
      l.material.color.setHex(l.userData.baseColor);
      l.material.opacity = l.userData.baseOpacity;
    }
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
    const touchesRoot = from === id || to === id;
    let color = 0x1a2028, opac = 0.08;
    if (touchesRoot) {
      if (to === id || up.has(from)) { color = 0xa9cdb4; opac = 0.95; }
      if (from === id || down.has(to)) { color = 0xe7ae8a; opac = 0.95; }
    } else if (up.has(from) && up.has(to)) { color = 0xa9cdb4; opac = 0.55; }
    else if (down.has(from) && down.has(to)) { color = 0xe7ae8a; opac = 0.55; }
    l.material.color.setHex(color);
    l.material.opacity = opac;
  }
}

function showInfoPanel(id) {
  document.getElementById('empty-info').hidden = !!id;
  document.getElementById('selected-info').hidden = !id;
  document.getElementById('function-picker').value = id || '';
  if (!id) { infoEl.classList.remove('visible'); return; }
  const mesh = nodeById.get(id);
  if (!mesh) { infoEl.classList.remove('visible'); return; }
  const n = mesh.userData.node;
  showEvidence?.(n);
  const peakTag = peakSet.has(id) ? ' · CALL ENTRY' : '';
  const pinnedTag = id === pinnedId ? ' · PINNED' : '';
  const up = bfsCone(id, callers); up.delete(id);
  const down = bfsCone(id, callees); down.delete(id);
  qEl.textContent = n.displayName || n.label || n.qname;
  subEl.textContent = `${n.qname} · ${n.file} · depth ${n.depth}${peakTag}${pinnedTag}`;
  descEl.textContent = n.description || `A function in ${n.file}. Select another point to follow its connections.`;
  statsEl.innerHTML = `
    <span>source lines in snapshot</span><b>${n.source_lines}</b>
    <span>direct callees</span><b>${n.n_callees}</b>
    <span>direct callers</span><b>${(callers.get(id) || []).length}</b>
    <span>estimated importance</span><b>${(n.importance || 0).toFixed(3)}</b>
    <span>purpose similarity</span><b>${((n.purpose_similarity || 0) * 100).toFixed(0)}%</b>
    <span>semantic density (relative)</span><b>${(n.semantic_density || 0).toFixed(3)}</b>
  `;

  conesEl.innerHTML = `
    <span class="up">↑ ${up.size} upstream function${up.size === 1 ? '' : 's'}</span>
    <span class="down">↓ ${down.size} downstream function${down.size === 1 ? '' : 's'}</span>
  `;
  infoEl.classList.add('visible');
}

// Hover previews a function only when a persistent selection is not active.
function setHover(id) {
  hoveredId = id;
  showInfoPanel(pinnedId || id);
  if (!pinnedId) paintFamilyTree(id);
}

function setPinned(id) {
  selectFunction(pinnedId === id ? null : id);
}

window.addEventListener('pointermove', (e) => {
  if (e.target.closest?.('[data-ui]')) return;
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(nodeMeshes, false);
  const nextId = hits.length ? hits[0].object.userData.node.id : null;
  if (nextId !== hoveredId) setHover(nextId);
});

// Click handler: if we hit a node, pin its family tree (toggle if same).
// If we hit nothing, unpin. We track mousedown position and only treat the
// click as valid if the pointer stayed within CLICK_SLOP pixels — otherwise
// it was a camera drag by OrbitControls, leave things alone.
let clickDownX = 0, clickDownY = 0;
const CLICK_SLOP = 5;
window.addEventListener('pointerdown', (e) => {
  clickDownX = e.clientX; clickDownY = e.clientY;
});
window.addEventListener('click', (e) => {
  const dx = e.clientX - clickDownX, dy = e.clientY - clickDownY;
  if (Math.hypot(dx, dy) > CLICK_SLOP) return;  // was a drag, not a click
  if (e.target && e.target.closest && e.target.closest('[data-ui]')) return;
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(mouse, camera);
  const hits = raycaster.intersectObjects(nodeMeshes, false);
  if (hits.length) {
    setPinned(hits[0].object.userData.node.id);
  } else if (pinnedId) {
    setPinned(pinnedId);  // same-id branch toggles off
  }
});

window.addEventListener('resize', () => {
  updateFraming();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ---------- control wiring ----------
for (const r of document.querySelectorAll('input[name="layout"]')) {
  r.checked = r.value === state.layout;
  r.addEventListener('change', () => { state.layout = r.value; updateURL({layout: r.value}); rebuild(); updateFraming(); selectFunction(pinnedId); });
}

function updateFraming() {
  const w = window.innerWidth, h = window.innerHeight;
  // Drain residual orbit motion before placing the camera, so Reset is exact.
  const damping = controls.enableDamping;
  controls.enableDamping = false;
  controls.update();
  controls.enableDamping = damping;
  camera.aspect = w / h;
  // Fit the actual functions into the space left by the paper controls. Reserve
  // the taller empty note even while selection changes, to avoid camera jumps.
  const mobile = w <= 860;
  const left = mobile ? 22 : 345, right = w - (mobile ? 22 : 40);
  const top = mobile ? 260 : 225, bottom = mobile ? h - 260 : h - 110;
  const availableW = Math.max(100, right - left), availableH = Math.max(120, bottom - top);
  camera.setViewOffset(w, h, w / 2 - (left + right) / 2, h / 2 - (top + bottom) / 2, w, h);
  const points = [...currentPositions.values()].map(p => new THREE.Vector3(p[0], p[1] + LIFT, p[2]));
  const surface = terrainMesh.geometry.getAttribute('position');
  const baseHeight = Math.min(...currentHeights.values());
  for (let i = 0; i < surface.count; i++) {
    if (surface.getY(i) > baseHeight + 0.02) points.push(new THREE.Vector3().fromBufferAttribute(surface, i));
  }
  const target = new THREE.Box3().setFromPoints(points).getCenter(new THREE.Vector3());
  const backward = new THREE.Vector3(0, 0.45, -1).normalize();
  const rightward = new THREE.Vector3().crossVectors(camera.up, backward).normalize();
  const upward = new THREE.Vector3().crossVectors(backward, rightward).normalize();
  const tanV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const tanH = tanV * camera.aspect;
  let distance = 30;
  for (const point of points) {
    const delta = point.clone().sub(target);
    const depth = delta.dot(backward);
    distance = Math.max(distance,
      depth + (Math.abs(delta.dot(rightward)) + 2) / (tanH * availableW / w),
      depth + (Math.abs(delta.dot(upward)) + 2) / (tanV * availableH / h));
  }
  camera.position.copy(target).addScaledVector(backward, distance * 1.08);
  controls.target.copy(target);
  camera.lookAt(target);
  controls.update();
  for (const line of edgeLines) line.material.resolution.set(w, h);
  camera.updateProjectionMatrix();
}

function selectFunction(id) {
  pinnedId = nodeById.has(id) ? id : null;
  hoveredId = null;
  paintFamilyTree(pinnedId);
  showInfoPanel(pinnedId);
  document.body.dataset.selectedNode = pinnedId || '';
  updateURL({node: pinnedId});
}

const picker = document.getElementById('function-picker');
for (const n of [...nodes].sort((a,b) => a.id.localeCompare(b.id))) {
  const option = document.createElement('option');
  option.value = n.id;
  option.textContent = saved ? n.qname : `${n.displayName || n.label} · ${n.file}:${n.location.start_line}`;
  picker.appendChild(option);
}
picker.addEventListener('change', () => selectFunction(picker.value));
document.getElementById('start-exploring').addEventListener('click', () => selectFunction(snapshot.entries?.find(id => nodeById.has(id)) || peakList[0]));
document.getElementById('clear-selection').addEventListener('click', () => selectFunction(null));
document.getElementById('reset-view').addEventListener('click', () => { updateFraming(); selectFunction(null); });
document.getElementById('graph-count').textContent = `${nodes.length} functions · ${edges.length} connections · ${saved ? 'saved example' : 'partial static map'}`;

const showEvidence = setupSnapshotUI(selectFunction);

rebuild();
updateFraming();
selectFunction(initialSelection);
await setupThemes((v, id) => {
  BOARD_BG.setStyle(v['board-bg-color']);
  scene.fog.color.copy(BOARD_BG);
  if (id !== 'canonical') {
    const low = new THREE.Color(v['board-bg-color']);
    const paper = new THREE.Color(v['nav-bg']);
    const high = paper.getHSL({}).l < .25 ? new THREE.Color(v['nav-ink']) : paper;
    TERRAIN_STOPS.forEach(([t, color]) => color.copy(low).lerp(high, .2 + .8 * t));
  } else {
    [0x536f65, 0x91afa0, 0xa4bec3, 0xccc7a6, 0xf5eedd].forEach((hex, i) => TERRAIN_STOPS[i][1].setHex(hex));
  }
  rebuild();
  selectFunction(pinnedId);
});

// OutputPass preserves the renderer's colour management on the transparent board.
const composer = new EffectComposer(renderer);
composer.setSize(window.innerWidth, window.innerHeight);
composer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new OutputPass());

window.addEventListener('resize', () => {
  composer.setSize(window.innerWidth, window.innerHeight);
});

// A few named landmarks make the first view readable before selection.
const landmarks = saved ? [] : [...nodes].sort((a, b) => b.importance - a.importance)
  .filter(n => !n.label.startsWith('$')).slice(0, 8).map(node => {
    const label = document.createElement('div');
    label.className = 'map-landmark paper';
    label.textContent = node.label.replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
    document.body.append(label);
    return {node, label};
  });
function placeLandmarks() {
  const occupied = [...document.querySelectorAll('[data-ui]')]
    .filter(el => !el.hidden).map(el => el.getBoundingClientRect());
  let visible = 0;
  for (const {node, label} of landmarks) {
    label.hidden = true;
    if (visible >= (innerWidth <= 860 ? 2 : 3) || node.id === pinnedId || node.id === hoveredId) continue;
    const mesh = nodeById.get(node.id);
    if (!mesh) continue;
    const p = mesh.position.clone().project(camera);
    const x = (p.x + 1) * innerWidth / 2, y = (1 - p.y) * innerHeight / 2 - 17;
    const box = {left: x - 80, right: x + 80, top: y - 28, bottom: y};
    if (Math.abs(p.z) > 1 || box.left < 8 || box.right > innerWidth - 8 || box.top < 8 || box.bottom > innerHeight - 8) continue;
    if (occupied.some(r => box.left < r.right && box.right > r.left && box.top < r.bottom && box.bottom > r.top)) continue;
    label.style.left = `${x}px`; label.style.top = `${y}px`; label.hidden = false;
    occupied.push(box); visible++;
  }
}

function animate() {
  requestAnimationFrame(animate);
  if (contextLost) return;
  controls.update();
  const label = document.getElementById('node-label');
  const selected = nodeById.get(pinnedId || hoveredId);
  label.hidden = !selected;
  if (selected) {
    const position = selected.position.clone().project(camera);
    label.hidden = Math.abs(position.x) > 1 || Math.abs(position.y) > 1 || Math.abs(position.z) > 1;
    label.textContent = selected.userData.node.displayName || selected.userData.node.qname;
    label.style.left = `${(position.x + 1) * window.innerWidth / 2}px`;
    label.style.top = `${(1 - position.y) * window.innerHeight / 2 - 14}px`;
  }
  placeLandmarks();
  composer.render();
}
animate();

document.body.dataset.renderer = 'webgl';
document.body.dataset.ready = 'true';
console.log(`loaded ${nodes.length} nodes, ${edges.length} edges, ${peakList.length} peaks, max_depth=${max_depth}`);
