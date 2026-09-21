export function classifyEntryBasins(nodes, parent, children, declaredEntrypoints = []) {
  const allRoots = nodes.filter(node => !parent.has(node.id)).map(node => node.id);
  const nodeIds = new Set(nodes.map(node => node.id));
  const declared = declaredEntrypoints.filter(id => nodeIds.has(id));

  // Adapters know why a symbol is executable from outside the analyzed graph
  // (route decorator, main method, event boundary). A missing incoming edge does
  // not provide that evidence: it can just as easily identify unused code or an
  // incomplete parse.
  let roots = declared.length
    ? declared
    : allRoots.filter(id => (children.get(id) || []).length > 0);
  if (!roots.length) roots = [...allRoots];

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
