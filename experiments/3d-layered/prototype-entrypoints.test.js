import test from 'node:test';
import assert from 'node:assert/strict';

import {chooseEntrypointForest, classifyEntryBasins} from './prototype-entrypoints.js';

test('a disconnected utility subgraph cannot become a project entry basin', () => {
  const nodes = [
    {id: 'route'},
    {id: 'pipeline'},
    {id: 'legacy-replacer'},
    {id: 'extract-coordinates'},
  ];
  const parent = new Map([
    ['pipeline', 'route'],
    ['extract-coordinates', 'legacy-replacer'],
  ]);
  const children = new Map(nodes.map(node => [node.id, []]));
  for (const [child, owner] of parent) children.get(owner).push(child);

  const result = classifyEntryBasins(nodes, parent, children, ['route']);

  assert.deepEqual(result.roots, ['route']);
  assert.deepEqual(new Set(result.detached), new Set(['legacy-replacer', 'extract-coordinates']));
});

test('a resolved call from reachable code promotes a secondary edge into the terrain', () => {
  const nodes = [
    {id: 'route'},
    {id: 'pipeline'},
    {id: 'legacy-replacer'},
    {id: 'shared-helper'},
    {id: 'legacy-leaf'},
  ];
  const edges = [
    {from: 'route', to: 'pipeline', primary: true, confidence: 'resolved', count: 1},
    {from: 'legacy-replacer', to: 'shared-helper', primary: true, confidence: 'resolved', count: 1},
    {from: 'pipeline', to: 'shared-helper', primary: false, confidence: 'resolved', count: 1},
    {from: 'legacy-replacer', to: 'legacy-leaf', primary: true, confidence: 'resolved', count: 1},
  ];

  const result = chooseEntrypointForest(nodes, edges, ['route']);

  assert.equal(result.parent.get('pipeline'), 'route');
  assert.equal(result.parent.get('shared-helper'), 'pipeline');
  assert.equal(result.parent.has('legacy-replacer'), false);
  assert.equal(result.parent.get('legacy-leaf'), 'legacy-replacer');
  assert.ok(result.primaryEdges.some(edge => edge.from === 'pipeline' && edge.to === 'shared-helper'));
});
