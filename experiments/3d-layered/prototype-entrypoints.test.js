import test from 'node:test';
import assert from 'node:assert/strict';

import {classifyEntryBasins} from './prototype-entrypoints.js';

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
