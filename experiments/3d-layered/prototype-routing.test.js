import test from 'node:test';
import assert from 'node:assert/strict';
import {circularRoute} from './prototype-routing.js';

const point = degree => ({x: 10 * Math.cos(degree * Math.PI / 180), y: 2, z: 10 * Math.sin(degree * Math.PI / 180)});
test('secondary routes cross the angular seam locally in both directions', () => {
  for (const [from, to] of [[359, 1], [1, 359]]) {
    const route = circularRoute(point(from), point(to));
    assert.ok(route.every(p => p.x > 9.99 && Math.abs(p.z) < .18));
    assert.ok(Math.abs(route[0].z - point(from).z) < 1e-10);
    assert.ok(Math.abs(route.at(-1).z - point(to).z) < 1e-10);
  }
});
test('circle routes retain radius instead of crossing the summit', () => {
  const route = circularRoute(point(0), point(180));
  assert.ok(route.every(p => Math.abs(Math.hypot(p.x, p.z) - 10) < 1e-10));
});
test('translated origin, project-center calls and recursion remain finite', () => {
  const a = {x: 30, y: 4, z: 20};
  const b = {x: 40, y: 1, z: 20};
  for (const route of [circularRoute(a, b, a), circularRoute(b, b, a)]) {
    assert.ok(route.every(p => [p.x, p.y, p.z].every(Number.isFinite)));
    assert.notDeepEqual(route[0], route[12]);
  }
});
