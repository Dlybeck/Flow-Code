function confidenceWeight(edge) {
  return edge.confidence === 'resolved' ? 1 : edge.confidence === 'heuristic' ? .68 : .38;
}

function compareEdges(a, b) {
  return Number(b.primary) - Number(a.primary)
    || confidenceWeight(b) - confidenceWeight(a)
    || (b.count || 0) - (a.count || 0)
    || a.from.localeCompare(b.from);
}

function chooseUnrootedForest(nodes, edges) {
  const byId = new Map(nodes.map(node => [node.id, node]));
  const incoming = new Map(nodes.map(node => [node.id, []]));
  for (const edge of edges) {
    if (byId.has(edge.from) && byId.has(edge.to)) incoming.get(edge.to).push(edge);
  }

  const parent = new Map();
  const primaryEdges = [];
  for (const node of nodes) {
    const candidates = incoming.get(node.id).sort(compareEdges);
    for (const edge of candidates) {
      let current = edge.from;
      let cyclic = current === node.id;
      while (!cyclic && parent.has(current)) {
        current = parent.get(current);
        cyclic = current === node.id;
      }
      if (!cyclic) {
        parent.set(node.id, edge.from);
        primaryEdges.push(edge);
        break;
      }
    }
  }
  return {parent, primaryEdges};
}

export function chooseEntrypointForest(nodes, edges, declaredEntrypoints = []) {
  const nodeIds = new Set(nodes.map(node => node.id));
  const validEdges = edges.filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to));
  const roots = [...new Set(declaredEntrypoints)].filter(id => nodeIds.has(id));
  if (!roots.length) return chooseUnrootedForest(nodes, validEdges);

  const parent = new Map();
  const primaryEdges = [];
  const reached = new Set(roots);
  const remaining = new Set(nodes.map(node => node.id).filter(id => !reached.has(id)));

  // Grow one execution layer at a time from verified entrypoints. An edge that
  // was previously secondary becomes primary when it is the best real route
  // from reached code into a new function.
  while (remaining.size) {
    const additions = [];
    for (const node of nodes) {
      if (!remaining.has(node.id)) continue;
      const candidate = validEdges
        .filter(edge => edge.to === node.id && reached.has(edge.from))
        .sort(compareEdges)[0];
      if (candidate) additions.push([node.id, candidate]);
    }
    if (!additions.length) break;
    for (const [id, edge] of additions) {
      parent.set(id, edge.from);
      primaryEdges.push(edge);
      reached.add(id);
      remaining.delete(id);
    }
  }

  // Preserve real relationships inside unreachable code without allowing that
  // code to claim a parent that is already part of the entrypoint terrain.
  const detachedNodes = nodes.filter(node => remaining.has(node.id));
  const detachedEdges = validEdges.filter(edge => remaining.has(edge.from) && remaining.has(edge.to));
  const detached = chooseUnrootedForest(detachedNodes, detachedEdges);
  for (const [child, owner] of detached.parent) parent.set(child, owner);
  primaryEdges.push(...detached.primaryEdges);

  return {parent, primaryEdges};
}

export function classifyEntryBasins(nodes, parent, children, declaredEntrypoints = []) {
  const nodeIds = new Set(nodes.map(node => node.id));
  const declared = declaredEntrypoints.filter(id => nodeIds.has(id));

  // Adapters know why a symbol is executable from outside the analyzed graph
  // (route decorator, main method, event boundary). A missing incoming edge does
  // not provide that evidence: it can just as easily identify unused code or an
  // incomplete parse.
  const roots = [...new Set(declared)];

  const reachable = new Set();
  const queue = [...roots];
  while (queue.length) {
    const id = queue.shift();
    if (reachable.has(id)) continue;
    reachable.add(id);
    queue.push(...(children.get(id) || []));
  }

  const detached = nodes.map(node => node.id).filter(id => !reachable.has(id));
  return {roots, detached};
}

export function validateFixture(fixture) {
  if (!fixture || typeof fixture.title !== 'string' || typeof fixture.purpose !== 'string'
      || !Array.isArray(fixture.nodes) || !fixture.nodes.length
      || !Array.isArray(fixture.edges) || !Array.isArray(fixture.entrypoints)) {
    throw new Error('Expected a Flow-Code prototype fixture with nodes, edges and entrypoints.');
  }
  const ids = new Set();
  for (const node of fixture.nodes) {
    if (!node || typeof node.id !== 'string' || !node.id || node.id === '__project__' || ids.has(node.id)
        || typeof node.label !== 'string' || typeof node.qname !== 'string'
        || !Number.isFinite(node.score) || node.score < 0 || node.score > 1) {
      throw new Error('Each function needs a unique ID, name and finite relevance score from 0 to 1.');
    }
    for (const field of ['similar', 'boundaries', 'entry_evidence']) {
      if (node[field] !== undefined && !Array.isArray(node[field])) throw new Error(`Function ${field} must be a list.`);
    }
    if ((node.similar || []).some(match => !match || typeof match.id !== 'string' || !Number.isFinite(match.cosine))) throw new Error('Invalid similarity evidence.');
    if ((node.boundaries || []).some(boundary => !boundary || typeof boundary !== 'object')) throw new Error('Invalid boundary evidence.');
    ids.add(node.id);
  }
  for (const edge of fixture.edges) {
    if (!edge || !ids.has(edge.from) || !ids.has(edge.to)
        || !['resolved', 'heuristic', 'unknown'].includes(edge.confidence)
        || (edge.count !== undefined && (!Number.isFinite(edge.count) || edge.count < 1))) {
      throw new Error('A relationship references a missing function or invalid confidence.');
    }
  }
  for (const field of ['source_roots', 'known_limits']) {
    if (fixture.coverage?.[field] !== undefined && !Array.isArray(fixture.coverage[field])) throw new Error(`Coverage ${field} must be a list.`);
  }
  if (fixture.entrypoints.some(id => !ids.has(id))) throw new Error('An entrypoint references a missing function.');
  return fixture;
}
