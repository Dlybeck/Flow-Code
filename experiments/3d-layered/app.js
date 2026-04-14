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
scene.background = new THREE.Color(0x0f1216);
scene.fog = new THREE.Fog(0x0f1216, 80, 200);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 700);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minPolarAngle = 0.05;
controls.maxPolarAngle = Math.PI * 0.48;

scene.add(new THREE.AmbientLight(0xffffff, 0.45));
const sun = new THREE.DirectionalLight(0xffffff, 0.85);
sun.position.set(20, 50, 20);
scene.add(sun);
const fill = new THREE.DirectionalLight(0x7aa5ff, 0.25);
fill.position.set(-20, 25, -15);
scene.add(fill);

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
// Dedicated rock color that steep faces mix toward regardless of elevation.
const ROCK = new THREE.Color(0x6a5c4f);

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

  // --- Terrain mesh --- (orphans excluded — they don't belong to the mountain)
  const terrainNodes = nodes.filter(n => !n.is_orphan);
  const pts2d = terrainNodes.map(n => {
    const [x, , z] = currentPositions.get(n.id);
    return [x, z];
  });
  const delaunay = Delaunay.from(pts2d);
  const triangles = delaunay.triangles;

  // Build positions, index, compute normals first — then color based on
  // both height AND slope steepness (steep faces bias toward rock).
  const posArr = new Float32Array(terrainNodes.length * 3);
  for (let i = 0; i < terrainNodes.length; i++) {
    const [x, y, z] = currentPositions.get(terrainNodes[i].id);
    posArr[i * 3] = x; posArr[i * 3 + 1] = y; posArr[i * 3 + 2] = z;
  }
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(posArr, 3));
  geom.setIndex(Array.from(triangles));
  geom.computeVertexNormals();

  // Read computed normals and build vertex colors with slope awareness
  const normals = geom.attributes.normal.array;
  const colArr = new Float32Array(terrainNodes.length * 3);
  for (let i = 0; i < terrainNodes.length; i++) {
    const [, y] = [posArr[i * 3], posArr[i * 3 + 1], posArr[i * 3 + 2]];
    const ny = normals[i * 3 + 1]; // vertical component of normal
    // steepness = 1 when normal horizontal (cliff), 0 when pointing straight up (flat)
    const steep = Math.max(0, 1 - Math.abs(ny));
    const t = (y - hMin) / hRange;
    const base = terrainColor(t);
    // Mix toward rock on any non-flat face. Our ski slope's gentlest edges are 20°,
    // so steep lands ~0.06 even at the shallowest; we want rock bleeding in there too.
    const rockMix = Math.min(1, Math.max(0, (steep - 0.05) * 3.2));
    const mixed = base.clone().lerp(ROCK, rockMix * 0.75);
    // Per-vertex noise — small (-0.05..+0.05) perturbation for texture
    const n = (hash(i) - 0.5) * 0.08;
    mixed.r = Math.max(0, Math.min(1, mixed.r + n));
    mixed.g = Math.max(0, Math.min(1, mixed.g + n));
    mixed.b = Math.max(0, Math.min(1, mixed.b + n));
    // Snow starts earlier and goes further — summits should read as white
    if (t > 0.78) {
      const snow = new THREE.Color(0xf8f5ef);
      const snowMix = (t - 0.78) / 0.22;
      mixed.lerp(snow, Math.min(1, snowMix * (1 - rockMix * 0.4)));
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

  // --- Edges (straight lines) — every call-graph edge is drawn, both primary-tree
  // and cross-edges (sideways / back-references). The line network you see IS
  // the call graph.
  for (const e of edges) {
    const a = currentPositions.get(e.from);
    const b = currentPositions.get(e.to);
    if (!a || !b) continue;
    const g = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(a[0], a[1] + LIFT, a[2]),
      new THREE.Vector3(b[0], b[1] + LIFT, b[2]),
    ]);
    const isPrimary = !!e.is_primary;
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({
      color: isPrimary ? 0x3a4450 : 0x555f6e,
      transparent: true,
      opacity: isPrimary ? 0.55 : 0.30,
    }));
    line.userData = { edge: e, baseOpacity: isPrimary ? 0.55 : 0.30 };
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
    camera.position.set(xMid, hMax + 25, zMid + 45);
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
  controls.update();
  renderer.render(scene, camera);
}
animate();

console.log(`loaded ${nodes.length} nodes, ${edges.length} edges, ${peakList.length} peaks, max_depth=${max_depth}`);
