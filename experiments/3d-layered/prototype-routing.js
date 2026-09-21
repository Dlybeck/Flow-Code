// Circular routes use the shortest angular displacement, including at ±π.
// Returned points are display geometry; they never influence execution height.
export function circularRoute(a, b, origin = {x: 0, z: 0}, steps = 24) {
  const ax = a.x - origin.x, az = a.z - origin.z;
  const bx = b.x - origin.x, bz = b.z - origin.z;
  const radiusA = Math.hypot(ax, az), radiusB = Math.hypot(bx, bz);
  let angleA = Math.atan2(az, ax), angleB = Math.atan2(bz, bx);
  if (radiusA < 1e-8) angleA = angleB;
  if (radiusB < 1e-8) angleB = angleA;
  const full = Math.PI * 2;
  const delta = ((angleB - angleA + Math.PI) % full + full) % full - Math.PI;
  const distance = Math.hypot(b.x - a.x, b.z - a.z);
  const self = distance < 1e-8 && Math.abs(b.y - a.y) < 1e-8;
  const lift = Math.min(5, 1.2 + distance * .12);
  return Array.from({length: steps + 1}, (_, index) => {
    const t = index / steps;
    const radius = radiusA + (radiusB - radiusA) * t;
    const angle = angleA + delta * t;
    return {
      x: self ? a.x + .9 * Math.sin(t * full) : origin.x + radius * Math.cos(angle),
      y: a.y + (b.y - a.y) * t + .45 + lift * Math.sin(Math.PI * t),
      z: self ? a.z + .9 * (1 - Math.cos(t * full)) : origin.z + radius * Math.sin(angle),
    };
  });
}
