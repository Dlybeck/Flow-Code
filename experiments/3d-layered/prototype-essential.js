// A presentation graph; the full fixture and its call evidence remain authoritative.
export function essentialView(full, {budget = 40, branchLimit = 6, revealed = new Set()} = {}) {
  const detached = new Set(full.orphans);
  const entries = new Set(full.children.get('__project__') || full.roots);
  const pathToEntry = id => {
    const path = [];
    while (id && id !== '__project__') { path.push(id); id = full.parent.get(id); }
    return path.reverse();
  };
  function buildProjection(anchors, revealedPath = new Set()) {
    const included = new Set(full.byId.has('__project__') ? ['__project__'] : []);
    for (const id of anchors) for (const step of pathToEntry(id)) included.add(step);
    const children = new Map([...included].map(id => [id, (full.children.get(id) || []).filter(c => included.has(c))]));
    const visible = new Set([...anchors, ...revealedPath]);
    for (const id of included) {
      if (entries.has(id) || id === '__project__' || children.get(id).length !== 1) visible.add(id);
    }
    const visibleAncestorByIncludedId = new Map();
    for (const id of included) {
      let cursor = id;
      while (cursor && !visible.has(cursor)) cursor = full.parent.get(cursor);
      if (cursor) visibleAncestorByIncludedId.set(id, cursor);
    }
    const nodes = [], byId = new Map(), heights = new Map(), scores = new Map(), parent = new Map();
    for (const original of full.nodes) {
      if (!visible.has(original.id)) continue;
      nodes.push(original); byId.set(original.id, original);
      heights.set(original.id, full.heights.get(original.id)); scores.set(original.id, full.scores.get(original.id));
    }
    const primaryEdges = [], representedPaths = new Map();
    for (const child of visible) {
      let owner = full.parent.get(child);
      while (owner && !visible.has(owner)) owner = full.parent.get(owner);
      if (!owner) continue;
      parent.set(child, owner);
      const steps = [child]; let cursor = child;
      while (cursor !== owner && full.parent.has(cursor)) { cursor = full.parent.get(cursor); steps.push(cursor); }
      steps.reverse();
      const evidence = steps.slice(1).map((id, i) => full.primaryEdges.find(e => e.from === steps[i] && e.to === id)).filter(Boolean);
      const grouping = owner === '__project__';
      const summarized = steps.length > 2;
      primaryEdges.push({from:owner, to:child, confidence: grouping ? 'grouping' : evidence.every(e => e.confidence === 'resolved') ? 'resolved' : 'heuristic', summarized, representedPath:steps, evidence});
      representedPaths.set(`${owner}|${child}`, steps);
    }
    const childMap = new Map(nodes.map(n => [n.id, []]));
    for (const [child, owner] of parent) childMap.get(owner).push(child);
    const roots = full.roots.map(id => visibleAncestorByIncludedId.get(id)).filter(Boolean);
    return {nodes, byId, heights, scores, parent, children:childMap, roots, representedPaths, primaryEdges, included, visibleAncestorByIncludedId};
  }
  const candidates = full.nodes.filter(n => n.id !== '__project__' && !detached.has(n.id))
    .sort((a,b) => b.score-a.score || a.id.localeCompare(b.id));
  const anchors = new Set(), branches = new Set(), reasons = new Map();
  for (const node of candidates) {
    const branch = pathToEntry(node.id)[0];
    if (!branches.has(branch) && branches.size >= branchLimit) continue;
    const duplicate = [...anchors].some(id => (node.similar || []).some(s => s.id === id && s.cosine >= .9)
      || (full.byId.get(id).similar || []).some(s => s.id === node.id && s.cosine >= .9));
    if (duplicate) continue;
    const proposed = new Set([...anchors, node.id]);
    const trial = buildProjection(proposed);
    if (trial.nodes.length - Number(full.byId.has('__project__')) > budget) continue;
    anchors.add(node.id); branches.add(branch); reasons.set(node.id, 'Project relevance; retained with its entry path');
  }
  // User exploration expands the automatic view without being cut by its budget.
  for (const id of revealed) if (full.byId.has(id) && !detached.has(id)) anchors.add(id);
  const revealedPath = new Set();
  for (const id of revealed) if (!detached.has(id)) for (const step of pathToEntry(id)) revealedPath.add(step);
  const view = buildProjection(anchors, revealedPath);
  const orphans = [...revealed].filter(id => detached.has(id));
  for (const id of orphans) {
    view.nodes.push(full.byId.get(id)); view.byId.set(id,full.byId.get(id)); view.children.set(id,[]);
    view.heights.set(id,full.heights.get(id)); view.scores.set(id,full.scores.get(id));
  }
  const visible = new Set(view.nodes.map(n => n.id));
  const secondaryEdges = [...full.secondaryEdges, ...full.primaryEdges.filter(e => detached.has(e.from) && detached.has(e.to))]
    .filter(e => visible.has(e.from) && visible.has(e.to));
  const drops = new Map([...view.parent].map(([child, owner]) => [child, view.heights.get(owner)-view.heights.get(child)]));
  const omitted = new Map();
  for (const n of full.nodes) {
    if (view.byId.has(n.id) || detached.has(n.id)) continue;
    let cursor = full.parent.get(n.id);
    while (cursor && !view.visibleAncestorByIncludedId.has(cursor)) cursor=full.parent.get(cursor);
    cursor=view.visibleAncestorByIncludedId.get(cursor);
    if (cursor) { if (!omitted.has(cursor)) omitted.set(cursor,[]); omitted.get(cursor).push(n.id); }
  }
  return {...full, ...view, full, essential:true, anchors, reasons, omitted, orphans, secondaryEdges, drops,
    unknownHighlights: full.nodes.filter(n => detached.has(n.id)).sort((a,b)=>b.score-a.score || a.id.localeCompare(b.id)).slice(0,5),
    violations: [...view.parent].filter(([c,p]) => view.heights.get(c)>view.heights.get(p))};
}
