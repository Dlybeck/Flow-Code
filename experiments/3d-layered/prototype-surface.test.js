import test from 'node:test';
import assert from 'node:assert/strict';
import {constrainedSurface,layoutSpines} from './prototype-surface.js';

test('terrain preserves a downhill spine beside higher neighboring terrain',()=>{
  const points=[{id:'a',x:0,z:0,y:10},{id:'b',x:4,z:0,y:2},{id:'c',x:2,z:1,y:15},{id:'d',x:2,z:-1,y:0}];
  const mesh=constrainedSurface(points,[{from:'a',to:'b',points:[points[0],{x:2,z:0,y:6},points[1]]}]);
  assert.equal(mesh.constraints.length,2);assert.ok(mesh.triangles.length);
});
test('invalid primary slopes and crossings fail visibly instead of using a free mesh',()=>{
  const p=[{id:'a',x:0,z:0,y:4},{id:'b',x:2,z:2,y:0},{id:'c',x:0,z:2,y:4},{id:'d',x:2,z:0,y:0}];
  assert.throws(()=>constrainedSurface(p,[{from:'a',to:'b',points:[p[0],p[1]]},{from:'c',to:'d',points:[p[2],p[3]]}]),/cross/);
  assert.throws(()=>constrainedSurface(p,[{from:'b',to:'a',points:[p[1],p[0]]}]),/uphill/);
});
test('circular sibling spines use common radial bands and descending samples',()=>{
  const nodes=['__project__','a','b','c'].map(id=>({id}));
  const m={nodes,primaryEdges:[],byId:new Map(nodes.map(n=>[n.id,n])),roots:['__project__'],children:new Map([['__project__',['a','b']],['a',['c']],['b',[]],['c',[]]]),scores:new Map(nodes.map(n=>[n.id,.5])),heights:new Map([['__project__',100],['a',95],['b',50],['c',94]]),orphans:[]};
  const result=layoutSpines(m);assert.equal(result.positions.get('a').radius,result.positions.get('b').radius);
  for(const path of result.routes.values())for(let i=1;i<path.length;i++)assert.ok(path[i].height<=path[i-1].height);
});
