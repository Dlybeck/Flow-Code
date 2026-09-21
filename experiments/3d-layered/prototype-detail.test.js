import test from 'node:test';
import assert from 'node:assert/strict';
import {chooseVisibleMarkers} from './prototype-detail.js';

test('dense summit keeps spaced markers without discarding source points', () => {
  const points = Array.from({length: 151}, (_, i) => ({id: String(i), x: 60 * Math.cos(i), y: 60 * Math.sin(i), priority: i / 151}));
  const snapshot = JSON.stringify(points);
  const visible = chooseVisibleMarkers(points);
  assert.ok(visible.size < 25);
  const shown = points.filter(p => visible.has(p.id));
  for (const a of shown) for (const b of shown) if (a !== b) assert.ok(Math.hypot(a.x - b.x, a.y - b.y) >= 28);
  assert.equal(JSON.stringify(points), snapshot);
  assert.deepEqual(chooseVisibleMarkers([...points].reverse()), visible);
});

test('zoom reveals nearby functions, with no importance threshold removing them', () => {
  const points = [{id:'important', x:0,y:0,priority:1}, {id:'bridge',x:12,y:0,priority:0}];
  assert.deepEqual([...chooseVisibleMarkers(points)], ['important']);
  assert.equal(chooseVisibleMarkers(points.map(p => ({...p,x:p.x*3}))).size, 2);
});

test('selection and its intermediate callers stay visible despite overlap', () => {
  const points = [{id:'caller', x:0,y:0,priority:0}, {id:'selected',x:1,y:0,priority:0}, {id:'other',x:2,y:0,priority:1}];
  const visible = chooseVisibleMarkers(points, {pinned: new Set(['caller','selected'])});
  assert.deepEqual(visible, new Set(['caller','selected']));
});
