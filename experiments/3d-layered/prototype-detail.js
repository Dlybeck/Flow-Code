// Screen-space detail only. This never edits graph structure, scores or heights.
export function chooseVisibleMarkers(points, {spacing = 28, pinned = new Set()} = {}) {
  const visible = new Set();
  const cells = new Map();
  const ordered = [...points].sort((a, b) => Number(pinned.has(b.id)) - Number(pinned.has(a.id))
    || b.priority - a.priority || a.id.localeCompare(b.id));
  for (const point of ordered) {
    const gx = Math.floor(point.x / spacing), gy = Math.floor(point.y / spacing);
    let occupied = false;
    for (let x = gx - 1; x <= gx + 1; x++) for (let y = gy - 1; y <= gy + 1; y++) {
      if ((cells.get(`${x},${y}`) || []).some(other => Math.hypot(point.x - other.x, point.y - other.y) < spacing)) occupied = true;
    }
    if (occupied && !pinned.has(point.id)) continue;
    visible.add(point.id);
    const key = `${gx},${gy}`;
    if (!cells.has(key)) cells.set(key, []);
    cells.get(key).push(point);
  }
  return visible;
}
