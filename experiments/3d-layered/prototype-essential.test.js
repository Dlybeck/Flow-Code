import test from 'node:test';
import assert from 'node:assert/strict';
import {essentialView} from './prototype-essential.js';
function chain() {
  const nodes = ['__project__','entry','a','b','core','unknown'].map((id,i)=>({id,label:id,qname:id,score:id==='core'?1:.1,similar:[]}));
  const parent=new Map([['entry','__project__'],['a','entry'],['b','a'],['core','b']]);
  const children=new Map(nodes.map(n=>[n.id,[]]));for(const [c,p] of parent)children.get(p).push(c);
  return {nodes,byId:new Map(nodes.map(n=>[n.id,n])),parent,children,roots:['__project__'],orphans:['unknown'],heights:new Map(nodes.map((n,i)=>[n.id,100-i*10])),scores:new Map(nodes.map(n=>[n.id,n.score])),primaryEdges:[...parent].map(([to,from])=>({from,to,confidence:'resolved'})),secondaryEdges:[],fixture:{edges:[]}};
}
test('budgeted overview condenses paths between real function nodes',()=>{
  const full=chain(), view=essentialView(full,{budget:3});
  assert.equal(view.nodes.length,4);
  assert.ok(view.nodes.every(node=>full.byId.has(node.id)));
  assert.ok(view.byId.has('a'));assert.ok(!view.byId.has('b'));
  assert.equal(view.heights.get('core'),full.heights.get('core'));
  assert.deepEqual(view.representedPaths.get('a|core'),['a','b','core']);
  assert.equal(view.primaryEdges.find(edge=>edge.from==='a'&&edge.to==='core').summarized,true);
  assert.equal(view.unknownHighlights[0].id,'unknown');assert.ok(!view.byId.has('unknown'));
  const expanded=essentialView(full,{budget:3,revealed:new Set(['core'])});
  assert.equal(expanded.nodes.length,5);assert.ok(expanded.byId.has('b'));
  assert.equal(expanded.heights.get('core'),view.heights.get('core'));
});
test('search can reveal an unplaced function without creating an entry',()=>{
  const full=chain(),view=essentialView(full,{revealed:new Set(['unknown'])});
  assert.ok(view.byId.has('unknown'));assert.ok(!view.parent.has('unknown'));assert.deepEqual(view.orphans,['unknown']);
});
test('branch limit and order are deterministic',()=>{
  const full=chain();full.nodes.reverse();
  assert.deepEqual([...essentialView(full,{budget:3}).anchors],[...essentialView({...full,nodes:[...full.nodes].reverse()},{budget:3}).anchors]);
});
test('a searched path restores every original caller even beyond the initial budget',()=>{
  const full=chain(),view=essentialView(full,{budget:3,revealed:new Set(['core'])});
  for(const id of ['entry','a','b','core'])assert.ok(view.byId.has(id));
});
test('six-branch cap, budget and omitted side branches are independently enforced',()=>{
  const full=chain();
  for(let i=0;i<12;i++){
    const id=`entry${i}`,n={id,label:id,qname:id,score:.9-i*.01,similar:[]};
    full.nodes.push(n);full.byId.set(id,n);full.parent.set(id,'__project__');full.children.get('__project__').push(id);full.children.set(id,[]);full.heights.set(id,90);full.scores.set(id,n.score);
    full.primaryEdges.push({from:'__project__',to:id,confidence:'resolved'});
  }
  const view=essentialView(full,{budget:8});
  assert.ok(view.nodes.length-1<=8);assert.equal(view.children.get('__project__').length,6);
  assert.ok(view.omitted.get('__project__').length>=6);
});
test('near-duplicate highlights are skipped but do not break required paths',()=>{
  const full=chain();
  full.byId.get('a').similar=[{id:'core',cosine:.95}];full.byId.get('b').similar=[{id:'core',cosine:.95}];
  const view=essentialView(full);
  assert.ok(!view.anchors.has('a'));assert.ok(!view.anchors.has('b'));
  assert.ok(!view.byId.has('a'));assert.ok(!view.byId.has('b'));
  assert.deepEqual(view.representedPaths.get('entry|core'),['entry','a','b','core']);
});
test('secondary returns and shared calls remain original relationships',()=>{
  const full=chain();full.secondaryEdges=[{from:'core',to:'entry',confidence:'resolved'},{from:'entry',to:'core',confidence:'heuristic'}];
  const view=essentialView(full,{budget:3});assert.deepEqual(view.secondaryEdges,full.secondaryEdges);
  assert.equal(view.parent.get('entry'),'__project__');
});

test('revealed unplaced calls survive as secondary relationships without entry paths',()=>{
  const full=chain();full.orphans=['a','b','core','unknown'];
  full.parent.delete('a');full.children.set('entry',[]);
  full.primaryEdges=full.primaryEdges.filter(e=>e.to!=='a');
  const view=essentialView(full,{revealed:new Set(['a','b'])});
  assert.deepEqual(view.secondaryEdges,[{from:'a',to:'b',confidence:'resolved'}]);
  assert.ok(!view.parent.has('a'));assert.ok(!view.parent.has('b'));
});
