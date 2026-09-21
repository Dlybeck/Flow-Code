import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Delaunay } from 'd3-delaunay';

export {chooseEntrypointForest, classifyEntryBasins} from './prototype-entrypoints.js';

const LOW = new THREE.Color(0x64877b);
const MID = new THREE.Color(0xa7c7b1);
const ROCK = new THREE.Color(0xdfca91);
const SNOW = new THREE.Color(0xfff4cb);
const GOLD = new THREE.Color(0xf4d06f);
const INK = new THREE.Color(0x163b35);
const MUTED = new THREE.Color(0x8ba49a);

function terrainColor(t) {
  if (t < .38) return LOW.clone().lerp(MID, t / .38);
  if (t < .76) return MID.clone().lerp(ROCK, (t - .38) / .38);
  return ROCK.clone().lerp(SNOW, (t - .76) / .24);
}

function descendants(root, children) {
  const found = new Set();
  const queue = [root];
  while (queue.length) {
    const id = queue.shift();
    if (found.has(id)) continue;
    found.add(id);
    queue.push(...(children.get(id) || []));
  }
  return found;
}

export function createTerrainView(canvas, onSelect) {
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: false});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  renderer.setClearColor(0x0a2521, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x0a2521, .008);
  scene.add(new THREE.HemisphereLight(0xfff4d5, 0x52766d, 2.6));
  const key = new THREE.DirectionalLight(0xffe9b0, 3.4);
  key.position.set(-18, 32, -12);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0xb8ddd4, 1.8);
  rim.position.set(24, 14, 20);
  scene.add(rim);

  const camera = new THREE.PerspectiveCamera(42, 1, .1, 300);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = .075;
  controls.minDistance = 15;
  controls.maxDistance = 90;
  controls.minPolarAngle = .18;
  controls.maxPolarAngle = Math.PI * .48;

  const world = new THREE.Group();
  scene.add(world);
  const nodeMeshes = [];
  const edgeLines = [];
  const labels = [];
  const nodeById = new Map();
  let currentModel = null;
  let currentPositions = new Map();
  let selectedId = null;
  let hoveredId = null;
  let focusTarget = null;

  const labelHost = canvas.parentElement;
  const relevanceKey = document.createElement('div');
  Object.assign(relevanceKey.style, {
    position: 'absolute', zIndex: '3', top: '12px', right: '12px',
    width: '190px', padding: '8px 10px', borderRadius: '7px',
    background: 'rgba(7,27,25,.84)', color: '#d5e5dd',
    font: '11px/1.3 ui-rounded, system-ui, sans-serif', pointerEvents: 'none',
  });
  const keyTitle = document.createElement('strong');
  keyTitle.textContent = 'NODE RELEVANCE';
  keyTitle.style.display = 'block';
  const keyGradient = document.createElement('i');
  Object.assign(keyGradient.style, {
    display: 'block', height: '6px', margin: '5px 0 4px', borderRadius: '999px',
    background: 'linear-gradient(90deg, #64877b, #f4d06f)',
  });
  const keyCopy = document.createElement('span');
  keyCopy.textContent = 'small green: low · larger gold: high · high descends gently';
  relevanceKey.append(keyTitle, keyGradient, keyCopy);
  labelHost.append(relevanceKey);

  const focusLabel = document.createElement('div');
  Object.assign(focusLabel.style, {
    position: 'absolute', zIndex: '4', pointerEvents: 'none',
    transform: 'translate(-50%, -115%)', width: 'max-content', maxWidth: '220px',
    padding: '5px 7px', borderRadius: '5px', background: '#f4d06f',
    color: '#173b35', boxShadow: '0 3px 9px #0007',
    font: '11px/1.25 ui-rounded, system-ui, sans-serif',
  });
  const focusTitle = document.createElement('strong');
  focusTitle.style.display = 'block';
  const focusMeta = document.createElement('span');
  focusMeta.style.display = 'block';
  focusMeta.style.marginTop = '2px';
  focusLabel.append(focusTitle, focusMeta);
  focusLabel.hidden = true;
  labelHost.append(focusLabel);

  function dispose(object) {
    object.traverse(child => {
      child.geometry?.dispose();
      if (Array.isArray(child.material)) child.material.forEach(material => material.dispose());
      else child.material?.dispose();
    });
  }

  function clearWorld() {
    dispose(world);
    world.clear();
    nodeMeshes.length = 0;
    edgeLines.length = 0;
    labels.splice(0).forEach(item => item.element.remove());
    focusTarget = null;
    focusLabel.hidden = true;
    nodeById.clear();
    currentPositions = new Map();
    hoveredId = null;
  }

  function scaledPositions(model) {
    const active = [...model.positions.entries()].filter(([id]) => !model.orphans.includes(id));
    const xs = active.map(([, p]) => p.x);
    const zs = active.map(([, p]) => p.y);
    const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs), 1);
    const scale = 34 / span;
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const values = active.map(([id]) => model.heights.get(id));
    const low = Math.min(...values);
    const high = Math.max(...values);
    const heightSpan = Math.max(1, high - low);
    const result = new Map();
    for (const node of model.nodes) {
      const point = model.positions.get(node.id);
      if (!point) continue;
      const height = model.heights.get(node.id) ?? low;
      const normalizedHeight = Math.max(0, (height - low) / heightSpan);
      result.set(node.id, new THREE.Vector3(
        (point.x - cx) * scale,
        1.4 + 15.5 * normalizedHeight,
        (point.y - cz) * scale,
      ));
    }
    return {positions: result, low, high};
  }

  function clusterRoots(model) {
    return model.roots.map(root => ({root, ids: descendants(root, model.children)}));
  }

  function buildTerrain(model, heightLow, heightHigh) {
    const heightSpan = Math.max(1, heightHigh - heightLow);
    for (const cluster of clusterRoots(model)) {
      const ids = [...cluster.ids].filter(id => currentPositions.has(id) && !model.orphans.includes(id));
      if (!ids.length) continue;
      const center = ids.reduce((sum, id) => sum.add(currentPositions.get(id)), new THREE.Vector3()).multiplyScalar(1 / ids.length);
      const radius = Math.max(4.5, ...ids.map(id => {
        const p = currentPositions.get(id);
        return Math.hypot(p.x - center.x, p.z - center.z);
      })) + 3.8;
      const points = ids.map(id => {
        const p = currentPositions.get(id);
        return {x: p.x, y: p.y, z: p.z, height: model.heights.get(id) ?? heightLow, apron: false};
      });
      const ringCount = Math.max(28, Math.min(56, ids.length * 2));
      for (let i = 0; i < ringCount; i++) {
        const angle = Math.PI * 2 * i / ringCount;
        const wobble = 1 + .045 * Math.sin(i * 2.37);
        points.push({
          x: center.x + radius * wobble * Math.cos(angle),
          y: .15,
          z: center.z + radius * wobble * Math.sin(angle),
          height: heightLow - 1,
          apron: true,
        });
      }
      const delaunay = Delaunay.from(points.map(point => [point.x, point.z]));
      const positions = [];
      const colors = [];
      for (const index of delaunay.triangles) {
        const point = points[index];
        positions.push(point.x, point.y, point.z);
        const t = point.apron ? 0 : Math.max(0, Math.min(1, (point.height - heightLow) / heightSpan));
        const color = terrainColor(t);
        colors.push(color.r, color.g, color.b);
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
      geometry.computeVertexNormals();
      const material = new THREE.MeshToonMaterial({vertexColors: true, flatShading: true, side: THREE.DoubleSide});
      const mesh = new THREE.Mesh(geometry, material);
      world.add(mesh);
      const creases = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry, 24),
        new THREE.LineBasicMaterial({color: 0x153d38, transparent: true, opacity: .2}),
      );
      world.add(creases);
    }
  }

  function addEdge(from, to, secondary = false) {
    const a = currentPositions.get(from);
    const b = currentPositions.get(to);
    if (!a || !b) return;
    let geometry;
    let arrowDirection = null;
    let arrowTip = null;
    if (secondary) {
      const distance = Math.hypot(b.x - a.x, b.z - a.z);
      const mid = a.clone().lerp(b, .5);
      mid.y = Math.max(a.y, b.y) + Math.min(5, 1.2 + distance * .12);
      const curve = new THREE.QuadraticBezierCurve3(
        a.clone().add(new THREE.Vector3(0, .45, 0)),
        mid,
        b.clone().add(new THREE.Vector3(0, .45, 0)),
      );
      const points = curve.getPoints(24);
      geometry = new THREE.BufferGeometry().setFromPoints(points);
      arrowTip = points.at(-1);
      arrowDirection = arrowTip.clone().sub(points.at(-2)).normalize();
    } else {
      geometry = new THREE.BufferGeometry().setFromPoints([
        a.clone().add(new THREE.Vector3(0, .42, 0)),
        b.clone().add(new THREE.Vector3(0, .42, 0)),
      ]);
    }
    const material = secondary
      ? new THREE.LineDashedMaterial({color: 0xb9c8bd, dashSize: .35, gapSize: .3, transparent: true, opacity: .58, depthWrite: false})
      : new THREE.LineBasicMaterial({color: 0x244b45, transparent: true, opacity: .9});
    const line = new THREE.Line(geometry, material);
    if (secondary) line.computeLineDistances();
    line.userData = {from, to, secondary};
    world.add(line);
    edgeLines.push(line);
    if (secondary && arrowDirection && arrowTip) {
      const arrow = new THREE.Mesh(
        new THREE.ConeGeometry(.13, .38, 8),
        new THREE.MeshBasicMaterial({color: 0xd5e5dc, transparent: true, opacity: .72, depthWrite: false}),
      );
      arrow.position.copy(arrowTip).addScaledVector(arrowDirection, -.19);
      arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), arrowDirection);
      world.add(arrow);
    }
  }

  function addNodes(model) {
    const orphanSet = new Set(model.orphans);
    const branchHeads = new Set(model.children.get('__project__') || model.roots);
    const geometry = new THREE.SphereGeometry(.34, 14, 10);
    for (const node of model.nodes) {
      const position = currentPositions.get(node.id);
      if (!position) continue;
      const project = node.id === '__project__';
      const orphan = orphanSet.has(node.id);
      const branch = branchHeads.has(node.id);
      const score = model.scores.get(node.id) ?? 0;
      const base = project ? SNOW.clone() : orphan ? MUTED.clone() : LOW.clone().lerp(GOLD, score);
      const material = new THREE.MeshStandardMaterial({
        color: base,
        roughness: .75,
        emissive: base.clone(),
        emissiveIntensity: .05,
        transparent: orphan,
        opacity: orphan ? .45 : 1,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.copy(position).add(new THREE.Vector3(0, .48, 0));
      mesh.scale.setScalar(project ? 2.1 : orphan ? .55 : .72 + score * .72);
      mesh.userData = {id: node.id, base, branch, score};
      nodeById.set(node.id, mesh);
      nodeMeshes.push(mesh);
      world.add(mesh);
      if (project) {
        const element = document.createElement('div');
        element.textContent = node.label;
        element.dataset.kind = 'project';
        Object.assign(element.style, {
          position: 'absolute', zIndex: '3', pointerEvents: 'none',
          transform: 'translate(-50%, -115%)', maxWidth: '170px',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          padding: '4px 7px', borderRadius: '4px', background: '#fff4cb',
          color: '#173b35', fontSize: '11px', fontWeight: '700',
          boxShadow: '0 2px 7px #0005',
        });
        canvas.parentElement.append(element);
        labels.push({element, mesh});
      }
    }
  }

  function update(model, {resetView = false} = {}) {
    currentModel = model;
    clearWorld();
    const scaled = scaledPositions(model);
    currentPositions = scaled.positions;
    buildTerrain(model, scaled.low, scaled.high);
    for (const [child, parent] of model.parent) addEdge(parent, child, false);
    for (const edge of model.secondaryEdges) addEdge(edge.from, edge.to, true);
    addNodes(model);
    select(selectedId);
    if (resetView) reset();
  }

  function showFocus(id) {
    const node = currentModel?.byId.get(id);
    const mesh = nodeById.get(id);
    if (!node || !mesh || id === '__project__') {
      focusTarget = null;
      focusLabel.hidden = true;
      return;
    }
    const score = currentModel.scores.get(id) ?? 0;
    const drop = currentModel.drops.get(id);
    const ownerId = currentModel.parent.get(id);
    const owner = ownerId ? currentModel.byId.get(ownerId) : null;
    focusTitle.textContent = `${id === selectedId ? 'SELECTED · ' : ''}${node.label}`;
    focusMeta.textContent = `relevance ${(score * 100).toFixed(0)}%${drop == null ? '' : ` · drops ${drop.toFixed(1)} from ${owner?.label || 'parent'}`}`;
    focusTarget = mesh;
    focusLabel.hidden = false;
  }

  function select(id) {
    selectedId = nodeById.has(id) ? id : null;
    for (const mesh of nodeMeshes) {
      const active = mesh.userData.id === selectedId;
      const highlighted = active && mesh.userData.id !== '__project__';
      mesh.material.color.copy(highlighted ? new THREE.Color(0xff8f70) : mesh.userData.base);
      mesh.material.emissive.copy(highlighted ? new THREE.Color(0xff8f70) : mesh.userData.base);
      mesh.material.emissiveIntensity = highlighted ? .4 : .05;
    }
    const family = new Set();
    if (selectedId && currentModel) {
      let idCursor = selectedId;
      while (currentModel.parent.has(idCursor)) {
        const parent = currentModel.parent.get(idCursor);
        family.add(`${parent}|${idCursor}`);
        idCursor = parent;
      }
    }
    for (const line of edgeLines) {
      const active = family.has(`${line.userData.from}|${line.userData.to}`);
      line.material.color.copy(active ? GOLD : line.userData.secondary ? new THREE.Color(0xb9c8bd) : INK);
      line.material.opacity = selectedId ? (active ? 1 : .28) : (line.userData.secondary ? .58 : .9);
    }
    showFocus(hoveredId || selectedId);
  }

  function reset() {
    const box = new THREE.Box3().setFromObject(world);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.z, size.y * 1.45, 18);
    controls.target.copy(center).add(new THREE.Vector3(0, size.y * .06, 0));
    camera.position.set(center.x - radius * .72, center.y + radius * .62, center.z + radius * .9);
    camera.lookAt(controls.target);
    controls.update();
  }

  function rotate(delta) {
    const offset = camera.position.clone().sub(controls.target);
    offset.applyAxisAngle(new THREE.Vector3(0, 1, 0), delta);
    camera.position.copy(controls.target).add(offset);
    camera.lookAt(controls.target);
    controls.update();
  }

  function resize() {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let press = null;
  function pickNode(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects(nodeMeshes, false)[0]?.object.userData.id || null;
  }
  canvas.addEventListener('pointerdown', event => { press = {x: event.clientX, y: event.clientY, dragged: false}; });
  canvas.addEventListener('pointermove', event => {
    if (press && Math.hypot(event.clientX - press.x, event.clientY - press.y) > 5) press.dragged = true;
    if (press?.dragged) return;
    hoveredId = pickNode(event);
    showFocus(hoveredId || selectedId);
  });
  canvas.addEventListener('pointerleave', () => {
    hoveredId = null;
    showFocus(selectedId);
  });
  canvas.addEventListener('pointerup', event => {
    if (!press || press.dragged || Math.hypot(event.clientX - press.x, event.clientY - press.y) > 5) { press = null; return; }
    press = null;
    const hit = pickNode(event);
    if (hit) onSelect?.(hit);
  });

  function frame() {
    requestAnimationFrame(frame);
    controls.update();
    const rect = canvas.getBoundingClientRect();
    let projectScreen = null;
    for (const {element, mesh} of labels) {
      const point = mesh.position.clone().project(camera);
      const visible = Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1 && Math.abs(point.z) <= 1;
      element.hidden = !visible;
      if (visible) {
        const x = canvas.offsetLeft + (point.x + 1) * rect.width / 2;
        const y = canvas.offsetTop + (1 - point.y) * rect.height / 2;
        element.style.left = `${x}px`;
        element.style.top = `${y}px`;
        projectScreen = {x, y};
      }
    }
    if (focusTarget) {
      const point = focusTarget.position.clone().project(camera);
      const visible = Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1 && Math.abs(point.z) <= 1;
      focusLabel.hidden = !visible;
      if (visible) {
        const x = canvas.offsetLeft + (point.x + 1) * rect.width / 2;
        let y = canvas.offsetTop + (1 - point.y) * rect.height / 2;
        const collides = projectScreen && Math.abs(x - projectScreen.x) < 120 && Math.abs(y - projectScreen.y) < 52;
        focusLabel.style.transform = collides ? 'translate(-50%, 12px)' : 'translate(-50%, -115%)';
        if (collides) y += 5;
        focusLabel.style.left = `${x}px`;
        focusLabel.style.top = `${y}px`;
      }
    }
    renderer.render(scene, camera);
  }
  frame();

  const api = {update, select, reset, rotate, scene, camera, controls, renderer, get model() { return currentModel; }};
  window.__terrain3d = api;
  return api;
}
