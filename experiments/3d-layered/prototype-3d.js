import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import {constrainedSurface} from './prototype-surface.js';
export {layoutSpines} from './prototype-surface.js';
export {essentialView} from './prototype-essential.js';
import {chooseVisibleMarkers} from './prototype-detail.js';
import {circularRoute} from './prototype-routing.js';

export {chooseEntrypointForest, classifyEntryBasins, validateFixture} from './prototype-entrypoints.js';

const LOW = new THREE.Color(0x64877b);
const MID = new THREE.Color(0xa7c7b1);
const ROCK = new THREE.Color(0xdfca91);
const SNOW = new THREE.Color(0xfff4cb);
const GOLD = new THREE.Color(0xf4d06f);
const INK = new THREE.Color(0x163b35);

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

export function createTerrainView(canvas, onSelect, onDetailChange) {
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
  const terrainMeshes = [];
  const labels = [];
  const nodeById = new Map();
  let currentModel = null;
  let currentPositions = new Map();
  let currentOrigin = {x: 0, z: 0};
  let currentTransform = null;
  let currentRoutes = new Map();
  let selectedId = null;
  let detail = 'overview';
  let detailSignature = '';
  let detailStatus = '';
  let selectedFamily = new Set();
  let revealedNodes = new Set();
  let allSecondary = false;
  let hoveredId = null;
  let focusTarget = null;

  const labelHost = canvas.parentElement;
  const relevanceKey = document.createElement('div');
  relevanceKey.dataset.kind = 'relevance-key';
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
  keyCopy.textContent = 'small green: low · larger gold: high · white ring: entry path unknown';
  relevanceKey.append(keyTitle, keyGradient, keyCopy);
  const lineKey = document.createElement('div');
  lineKey.style.marginTop = '7px';
  for (const [label, pattern] of [['Direct call', ''], ['Supporting steps', '12 3'], ['Additional call →', '1 5'], ['Project membership', '4 6']]) {
    const row = document.createElement('div');
    Object.assign(row.style, {display: 'flex', alignItems: 'center', gap: '7px', marginTop: '2px'});
    const sample = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    sample.setAttribute('width', '28'); sample.setAttribute('height', '8');
    const stroke = document.createElementNS(sample.namespaceURI, 'line');
    for (const [key, value] of Object.entries({x1: '0', x2: '28', y1: '4', y2: '4', stroke: '#d5e5dd', 'stroke-width': '2', 'stroke-dasharray': pattern})) stroke.setAttribute(key, value);
    sample.append(stroke); row.append(sample, document.createTextNode(label)); lineKey.append(row);
  }
  relevanceKey.append(lineKey);
  labelHost.append(relevanceKey);

  const focusLabel = document.createElement('div');
  focusLabel.dataset.kind = 'focus';
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
    terrainMeshes.length = 0;
    labels.splice(0).forEach(item => { item.element.remove(); item.leader?.remove(); });
    focusTarget = null;
    focusLabel.hidden = true;
    nodeById.clear();
    currentPositions = new Map();
    hoveredId = null;
  }

  function scaledPositions(model) {
    let active = [...model.positions.entries()].filter(([id]) => !model.orphans.includes(id));
    if (!active.length) active = [...model.positions.entries()];
    const xs = active.map(([, p]) => p.x);
    const zs = active.map(([, p]) => p.y);
    const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...zs) - Math.min(...zs), 1);
    const scale = 34 / span;
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
    const values = active.map(([id]) => model.heights.get(id));
    const low = model.heightRange?.low ?? Math.min(...values);
    const high = model.heightRange?.high ?? Math.max(...values);
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
    currentTransform = p => new THREE.Vector3((p.x-cx)*scale,1.4+15.5*Math.max(0,(p.height-low)/heightSpan),(p.z-cz)*scale);
    return {positions: result, low, high, origin: {x: -cx * scale, z: -cz * scale}};
  }

  function clusterRoots(model) {
    return model.roots.map(root => ({root, ids: descendants(root, model.children)}));
  }

  function buildTerrain(model, heightLow, heightHigh) {
    const ids=model.nodes.map(n=>n.id).filter(id=>currentPositions.has(id)&&!model.orphans.includes(id));
    if(!ids.length)return;
    const points=ids.map(id=>({id,...currentPositions.get(id)}));
    const center=points.reduce((sum,p)=>sum.add(new THREE.Vector3(p.x,0,p.z)),new THREE.Vector3()).multiplyScalar(1/points.length);
    const radius=Math.max(4.5,...points.map(p=>Math.hypot(p.x-center.x,p.z-center.z)))+3.8;
    for(let i=0;i<40;i++){
      const angle=2*Math.PI*i/40;
      points.push({id:`__apron_${i}`,x:center.x+radius*Math.cos(angle),y:.15,z:center.z+radius*Math.sin(angle),apron:true});
    }
    const paths=[];currentRoutes=new Map();
    for(const [key,route] of model.routes){
      const vertices=route.map(currentTransform);currentRoutes.set(key,vertices);
      const [child,owner]=[...model.parent].find(([c,p])=>`${p}|${c}`===key)||[];
      if(owner&&child)paths.push({from:owner,to:child,points:vertices});
    }
    const meshData=constrainedSurface(points,paths);
    const positions=[],colors=[];
    for(const triangle of meshData.triangles)for(const index of triangle){
      const p=meshData.vertices[index];positions.push(p.x,p.y,p.z);
      const color=terrainColor(Math.max(0,Math.min(1,(p.y-1.4)/15.5)));colors.push(color.r,color.g,color.b);
    }
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
    geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geometry.computeVertexNormals();
    const mesh=new THREE.Mesh(geometry,new THREE.MeshToonMaterial({vertexColors:true,flatShading:true,side:THREE.DoubleSide}));
    mesh.userData.terrain=true;mesh.userData.constraints=meshData.constraints.length;
    terrainMeshes.push(mesh);world.add(mesh);
    // Lighting and flat-shaded facets provide depth; polygon edges are not calls.
  }

  function addEdge(from, to, secondary = false, confidence = "resolved") {
    const a = currentPositions.get(from);
    const b = currentPositions.get(to);
    if (!a || !b) return;
    let geometry;
    let arrowDirection = null;
    let arrowTip = null;
    if (secondary) {
      const points = circularRoute(a, b, currentOrigin).map(p => new THREE.Vector3(p.x, p.y, p.z));
      geometry = new THREE.BufferGeometry().setFromPoints(points);
      arrowTip = points.at(-1);
      arrowDirection = arrowTip.clone().sub(points.at(-2)).normalize();
    } else {
      const route=currentRoutes.get(`${from}|${to}`)||[a,b];
      geometry = new THREE.BufferGeometry().setFromPoints(route.map(p=>p.clone().add(new THREE.Vector3(0,.42,0))));
    }
    const summarized=currentModel.primaryEdges.find(e=>e.from===from&&e.to===to)?.summarized;
    const kind = secondary ? 'secondary' : from === '__project__' ? 'grouping' : summarized ? 'collapsed' : 'primary';
    const pattern = {secondary: [.08, .3], grouping: [.24, .34], collapsed: [.85, .22]}[kind];
    const material = pattern
      ? new THREE.LineDashedMaterial({color: 0xb9c8bd, dashSize: pattern[0], gapSize: pattern[1], transparent: true, opacity: .58, depthWrite: false})
      : new THREE.LineBasicMaterial({color: 0x244b45, transparent: true, opacity: .9});
    const line = new THREE.Line(geometry, material);
    if (pattern) line.computeLineDistances();
    line.userData = {from, to, secondary, confidence, kind};
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
      line.userData.arrow = arrow;
    }
  }

  function addNodes(model) {
    const orphanSet = new Set(model.orphans);
    const branchHeads = new Set(model.children.get('__project__') || model.roots);
    const landmarks = new Set(model.nodes.filter(n => branchHeads.has(n.id) && !orphanSet.has(n.id))
      .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id)).slice(0, 24).map(n => n.id));
    const geometry = new THREE.SphereGeometry(.34, 14, 10);
    for (const node of model.nodes) {
      const position = currentPositions.get(node.id);
      if (!position) continue;
      const project = node.id === '__project__';
      const orphan = orphanSet.has(node.id);
      const branch = branchHeads.has(node.id);
      const score = model.scores.get(node.id) ?? 0;
      const base = project ? SNOW.clone() : LOW.clone().lerp(GOLD, score);
      const material = new THREE.MeshStandardMaterial({
        color: base,
        roughness: .75,
        emissive: base.clone(),
        emissiveIntensity: .05,
        transparent: false,
        opacity: 1,
      });
      const mesh = new THREE.Mesh(node.kind === 'supporting-group' ? new THREE.OctahedronGeometry(.44) : geometry, material);
      mesh.position.copy(position).add(new THREE.Vector3(0, .48, 0));
      mesh.scale.setScalar(project ? 2.1 : .72 + score * .72);
      mesh.userData = {id: node.id, base, branch, score, relevance: node.score};
      nodeById.set(node.id, mesh);
      nodeMeshes.push(mesh);
      world.add(mesh);
      if (orphan) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(.49, .045, 4, 16), new THREE.MeshBasicMaterial({color: 0xd8e5dd}));
        ring.rotation.x = Math.PI / 2;
        mesh.add(ring);
      }
      if (project || node.kind === 'supporting-group' || landmarks.has(node.id)) {
        const element = document.createElement(project ? 'div' : 'button');
        element.textContent = project || node.kind === 'supporting-group' ? node.label : `Entry · ${node.label}`;
        element.title = node.qname;
        element.dataset.kind = project ? 'project' : node.kind === 'supporting-group' ? 'group' : 'entry';
        if (!project) element.addEventListener('click', () => onSelect?.(node.id));
        Object.assign(element.style, {
          position: 'absolute', zIndex: '3', pointerEvents: project ? 'none' : 'auto',
          transform: 'translate(-50%, -115%)', maxWidth: '170px',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          padding: '4px 7px', borderRadius: '4px', background: '#fff4cb',
          color: '#173b35', fontSize: '11px', fontWeight: '700',
          boxShadow: '0 2px 7px #0005',
        });
        canvas.parentElement.append(element);
        let leader = null;
        if (!project) {
          leader = document.createElement('span');
          Object.assign(leader.style, {position: 'absolute', zIndex: '2', pointerEvents: 'none', height: '1px', background: '#f8f1d980', transformOrigin: 'left center'});
          canvas.parentElement.append(leader);
        }
        labels.push({element, mesh, leader});
      }
    }
  }

  function update(model, {resetView = false} = {}) {
    currentModel = model;
    clearWorld();
    currentRoutes=new Map();
    if(!model.nodes.length){detailSignature='';onDetailChange?.('No entry paths established. Search the complete inventory below.');return;}
    const scaled = scaledPositions(model);
    currentPositions = scaled.positions;
    currentOrigin = scaled.origin;
    buildTerrain(model, scaled.low, scaled.high);
    const evidence = new Map(model.primaryEdges.map(e => [`${e.from}|${e.to}`, e.confidence]));
    for (const [child, parent] of model.parent) addEdge(parent, child, model.orphans.includes(child), evidence.get(`${parent}|${child}`) || 'grouping');
    for (const edge of model.secondaryEdges) addEdge(edge.from, edge.to, true, edge.confidence);
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
    focusMeta.textContent = currentModel.orphans.includes(id) ? 'Entry path not established · inspect known calls' : `relevance ${(score * 100).toFixed(0)}%${drop == null ? '' : ` · drops ${drop.toFixed(1)} from ${owner?.label || 'parent'}`}`;
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
    detailSignature = '';
    selectedFamily = new Set(selectedId ? [selectedId] : []);
    const family = new Set();
    if (selectedId && currentModel) {
      let idCursor = selectedId;
      while (currentModel.parent.has(idCursor)) {
        const parent = currentModel.parent.get(idCursor);
        family.add(`${parent}|${idCursor}`);
        selectedFamily.add(parent);
        idCursor = parent;
      }
    }
    revealedNodes = new Set(selectedFamily);
    for (const line of edgeLines) {
      const active = family.has(`${line.userData.from}|${line.userData.to}`);
      const incident = line.userData.from === selectedId || line.userData.to === selectedId;
      if (incident && selectedId !== '__project__' || line.userData.secondary && allSecondary) {
        revealedNodes.add(line.userData.from); revealedNodes.add(line.userData.to);
      }
      line.userData.active = active;
      line.userData.incident = incident;
      line.visible = !line.userData.secondary || allSecondary || incident;
      if (line.userData.arrow) line.userData.arrow.visible = line.visible;
      const inferred = line.userData.confidence === 'heuristic';
      const baseColor = inferred ? new THREE.Color(0xe8a766) : line.userData.kind === 'grouping' ? new THREE.Color(0x789789) : line.userData.secondary ? new THREE.Color(0xb9c8bd) : INK;
      line.material.color.copy(active ? GOLD : baseColor);
      line.material.opacity = selectedId && selectedId !== '__project__' ? (active || incident ? 1 : .22) : (line.userData.secondary ? .48 : .8);
    }
    showFocus(hoveredId || selectedId);
  }

  function reset() {
    // Fit the actual terrain vertices, not invisible secondary arcs. A sphere
    // around the whole scene wastes most of the canvas on empty space.
    const points = terrainMeshes.flatMap(mesh => {
      const vertices = mesh.geometry.getAttribute('position');
      return Array.from({length: vertices.count}, (_, i) => new THREE.Vector3().fromBufferAttribute(vertices, i));
    });
    if (!points.length) points.push(...currentPositions.values());
    const box = new THREE.Box3().setFromPoints(points);
    const center = box.getCenter(new THREE.Vector3());
    const entries = currentModel.children.get('__project__') || currentModel.roots;
    const prominent = [...entries].sort((a, b) => (currentModel.byId.get(b)?.score || 0) - (currentModel.byId.get(a)?.score || 0))[0];
    const entryPosition = currentPositions.get(prominent);
    // Face the highest-scoring entry without changing the terrain or its links.
    const direction = entryPosition ? new THREE.Vector3(entryPosition.x - currentOrigin.x, 0, entryPosition.z - currentOrigin.z).normalize() : new THREE.Vector3(-.62, 0, .78);
    direction.y = .62; direction.normalize();
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), direction).normalize();
    const up = new THREE.Vector3().crossVectors(direction, right);
    const tanY = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const tanX = tanY * camera.aspect;
    let distance = 18;
    for (const point of points) {
      const offset = point.clone().sub(center);
      distance = Math.max(distance, offset.dot(direction) + Math.abs(offset.dot(right)) / tanX,
        offset.dot(direction) + Math.abs(offset.dot(up)) / tanY);
    }
    distance *= 1.12;
    controls.maxDistance = Math.max(90, distance * 1.5);
    controls.target.copy(center);
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.lookAt(controls.target);
    // Center the projected terrain, whose footprint is asymmetric in perspective.
    for (let iteration = 0; iteration < 2; iteration++) {
      camera.updateMatrixWorld(true);
      const projected = points.map(point => point.clone().project(camera));
      const centerX = (Math.min(...projected.map(p => p.x)) + Math.max(...projected.map(p => p.x))) / 2;
      const centerY = (Math.min(...projected.map(p => p.y)) + Math.max(...projected.map(p => p.y))) / 2;
      const pan = right.clone().multiplyScalar(centerX * distance * tanX).addScaledVector(up, centerY * distance * tanY);
      controls.target.add(pan); camera.position.add(pan);
    }
    const damping = controls.enableDamping;
    controls.enableDamping = false;
    controls.update();
    controls.enableDamping = damping;
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
    const hit = raycaster.intersectObjects(nodeMeshes.filter(mesh => mesh.visible), false)[0];
    if (!hit) return null;
    const surface = raycaster.intersectObjects(terrainMeshes, false)[0];
    return !surface || hit.distance <= surface.distance ? hit.object.userData.id : null;
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

  function updateDetail(rect) {
    if (!currentModel) return;
    camera.updateMatrixWorld(true);
    const signature = `${camera.matrixWorld.elements.join(',')}|${camera.projectionMatrix.elements.join(',')}|${rect.width}|${rect.height}|${detail}`;
    if (signature === detailSignature) return;
    detailSignature = signature;
    const points = nodeMeshes.map(mesh => {
      const p = mesh.position.clone().project(camera);
      return {id: mesh.userData.id, x: (p.x + 1) * rect.width / 2, y: (1 - p.y) * rect.height / 2,
        priority: mesh.userData.relevance, onScreen: Math.abs(p.x) <= 1 && Math.abs(p.y) <= 1 && Math.abs(p.z) <= 1};
    });
    const pinned = new Set(['__project__', ...revealedNodes]);
    const visible = detail === 'all' || currentModel.essential ? new Set(nodeMeshes.map(mesh => mesh.userData.id))
      : chooseVisibleMarkers(points.filter(p => p.onScreen), {pinned, spacing: 28});
    // A selected path is never simplified, including its lower-scoring bridges.
    for (const id of revealedNodes) visible.add(id);
    for (const mesh of nodeMeshes) mesh.visible = visible.has(mesh.userData.id);
    if (hoveredId && !visible.has(hoveredId)) { hoveredId = null; showFocus(selectedId); }
    for (const line of edgeLines) {
      const {from, to, secondary, active, incident} = line.userData;
      line.visible = secondary ? (allSecondary || incident)
        : currentModel.essential || detail === 'all' || active || (incident && selectedId !== '__project__') || (visible.has(from) && visible.has(to));
      if (line.userData.arrow) line.userData.arrow.visible = line.visible;
    }
    const shown = points.filter(p => p.id !== '__project__' && p.onScreen && visible.has(p.id)).length;
    const total = currentModel.nodes.filter(n => n.id !== '__project__').length;
    const status = currentModel.essential ? `Essential · ${total} items, including ${currentModel.groups.size} supporting groups. Expand groups or search to explore more.` : detail === 'all' ? `All ${total} function markers enabled.`
      : `Overview · ${shown} of ${total} function markers in view. Zoom to reveal more; select to trace every step.`;
    if (status !== detailStatus) { detailStatus = status; onDetailChange?.(status); }
  }

  function frame() {
    requestAnimationFrame(frame);
    controls.update();
    const rect = canvas.getBoundingClientRect();
    updateDetail(rect);
    let projectScreen = null;
    const keyBox = relevanceKey.getBoundingClientRect();
    const hostBox = labelHost.getBoundingClientRect();
    const occupied = [{left: keyBox.left - hostBox.left, right: keyBox.right - hostBox.left,
      top: keyBox.top - hostBox.top, bottom: keyBox.bottom - hostBox.top}];
    labels.sort((a, b) => Number(b.element.dataset.kind === 'project') - Number(a.element.dataset.kind === 'project') || b.mesh.userData.score - a.mesh.userData.score);
    let landmarkCount = 0;
    for (const {element, mesh, leader} of labels) {
      const point = mesh.position.clone().project(camera);
      let visible = mesh.visible && Math.abs(point.x) <= 1 && Math.abs(point.y) <= 1 && Math.abs(point.z) <= 1;
      const project = element.dataset.kind === 'project';
      if (!project && (mesh.userData.id === selectedId || mesh.userData.id === hoveredId)) visible = false;
      if (visible && !project) {
        const direction = mesh.position.clone().sub(camera.position);
        const distance = direction.length();
        raycaster.set(camera.position, direction.normalize());
        if (raycaster.intersectObjects(terrainMeshes, false).some(hit => hit.distance < distance - .5)) visible = false;
      }
      if (!project && landmarkCount >= (rect.width < 500 ? 3 : 6)) visible = false;
      element.hidden = !visible;
      if (leader) leader.hidden = !visible;
      if (visible) {
        const x = canvas.offsetLeft + (point.x + 1) * rect.width / 2;
        const y = canvas.offsetTop + (1 - point.y) * rect.height / 2;
        const width = element.offsetWidth, height = element.offsetHeight;
        const candidates = project ? [{x, y}] : [{x: x + 108, y: y - 28}, {x: x - 108, y: y - 28}, {x: x + 108, y: y + 42}, {x: x - 108, y: y + 42}, {x, y: y - 72}, {x, y: y + 85}];
        const chosen = candidates.map(position => ({...position, left: position.x - width / 2, right: position.x + width / 2, top: position.y - height * 1.15, bottom: position.y}))
          .find(box => (box.left >= 8 && box.right <= rect.width - 8 && box.top >= 8 && box.bottom < rect.height - 40
            && !occupied.some(other => box.left < other.right + 6 && box.right > other.left - 6 && box.top < other.bottom + 6 && box.bottom > other.top - 6)));
        if (!chosen) { element.hidden = true; if (leader) leader.hidden = true; continue; }
        element.style.left = `${chosen.x}px`; element.style.top = `${chosen.y}px`;
        occupied.push(chosen);
        if (project) projectScreen = {x, y};
        else {
          landmarkCount++;
          const targetY = chosen.y - height / 2;
          leader.style.left = `${x}px`; leader.style.top = `${y}px`;
          leader.style.width = `${Math.hypot(chosen.x - x, targetY - y)}px`;
          leader.style.transform = `rotate(${Math.atan2(targetY - y, chosen.x - x)}rad)`;
        }
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
        let focusBox = focusLabel.getBoundingClientRect();
        if (focusBox.left < keyBox.right + 6 && focusBox.right > keyBox.left - 6 && focusBox.top < keyBox.bottom + 6 && focusBox.bottom > keyBox.top - 6) {
          focusLabel.style.transform = 'translate(-50%, 0)';
          focusLabel.style.top = `${keyBox.bottom - hostBox.top + 8}px`;
          focusBox = focusLabel.getBoundingClientRect();
        }
        for (const {element, leader} of labels) {
          if (element.hidden) continue;
          const box = element.getBoundingClientRect();
          if (box.left < focusBox.right + 6 && box.right > focusBox.left - 6 && box.top < focusBox.bottom + 6 && box.bottom > focusBox.top - 6) { element.hidden = true; if (leader) leader.hidden = true; }
        }
      }
    }
    renderer.render(scene, camera);
  }
  frame();

  function focus(id) {
    const point = currentPositions.get(id);
    if (!point) return;
    const offset = camera.position.clone().sub(controls.target);
    controls.target.copy(point);
    camera.position.copy(point).add(offset);
    controls.update();
  }

  const api = {update, select, reset, rotate, focus, setDetail(value) { detail = value === 'all' ? 'all' : 'overview'; detailSignature = ''; }, showAllSecondary(value) { allSecondary = Boolean(value); select(selectedId); }, scene, camera, controls, renderer, get model() { return currentModel; }};
  window.__terrain3d = api;
  return api;
}
