import cdt2d from 'cdt2d';

export function layoutSpines(model) {
  const positions=new Map(), routes=new Map(), ranges=new Map(), sizes=new Map();
  const size=id=>{if(!sizes.has(id))sizes.set(id,1+(model.children.get(id)||[]).reduce((n,c)=>n+size(c),0));return sizes.get(id);};
  model.roots.forEach(size);
  const rotation=model.seamRotation || 0;
  const put=(id,radius,angle)=>positions.set(id,{x:radius*Math.cos(angle+rotation),y:radius*Math.sin(angle+rotation),radius,angle:angle+rotation});
  const anchor=model.byId.has('__project__');
  model.roots.forEach((root,i)=>{
    const angle=2*Math.PI*(i+.5)/Math.max(1,model.roots.length);
    put(root,anchor?0:82,anchor?0:angle);
    ranges.set(root,anchor?[0,2*Math.PI]:[angle-Math.PI/model.roots.length,angle+Math.PI/model.roots.length]);
  });
  function place(owner) {
    const kids=model.children.get(owner)||[];if(!kids.length)return;
    const [start,end]=ranges.get(owner), total=kids.reduce((n,c)=>n+Math.sqrt(size(c)),0);
    const a=positions.get(owner);let cursor=start;
    const step=(owner==='__project__' && model.essential ? 2 : 1)*Math.max(...kids.map(child=>{
      const edge=model.primaryEdges.find(e=>e.from===owner&&e.to===child);
      const confidence=edge?.confidence==='resolved'?1:edge?.confidence==='heuristic'?.68:.75;
      return 48+18*(1-confidence)+15*Math.abs((model.scores.get(owner)??1)-(model.scores.get(child)??0));
    }));
    for(const child of kids){
      const width=(end-start)*Math.sqrt(size(child))/total, angle=cursor+width/2;
      put(child,a.radius+step,angle);ranges.set(child,[cursor,cursor+width]);cursor+=width;
      const b=positions.get(child);
      // Subdivide the radial band at the same fractions for all siblings.
      // A source at radius zero has no direction; leave along the child's ray.
      const fromAngle=a.radius===0?b.angle:a.angle;
      const samples=48;
      const route=Array.from({length:samples+1},(_,i)=>{
        const t=i/samples,r=a.radius+(b.radius-a.radius)*t,theta=fromAngle+(b.angle-fromAngle)*t;
        return {x:r*Math.cos(theta),z:r*Math.sin(theta),height:model.heights.get(owner)+(model.heights.get(child)-model.heights.get(owner))*t};
      });
      routes.set(`${owner}|${child}`,route);
    }
    kids.forEach(place);
  }
  model.roots.forEach(place);
  const radius=Math.max(0,...[...positions.values()].map(p=>p.radius));
  model.orphans.forEach((id,i)=>put(id,radius+60+18*(i%2),Math.PI*.58+Math.PI*.84*(i+.5)/Math.max(1,model.orphans.length)));
  return {...model,positions,routes};
}

function orientation(a,b,c){return (b.x-a.x)*(c.z-a.z)-(b.z-a.z)*(c.x-a.x);}
export function constrainedSurface(points, paths) {
  const vertices=points.map(p=>({...p})), constraints=[], index=new Map(vertices.map((p,i)=>[p.id,i]));
  for(const path of paths){
    let previous=index.get(path.from);
    if(previous===undefined||!index.has(path.to))throw new Error('Terrain path has a missing endpoint');
    for(let j=1;j<path.points.length;j++){
      const next=j===path.points.length-1?index.get(path.to):vertices.push({...path.points[j]})-1;
      if(Math.hypot(vertices[previous].x-vertices[next].x,vertices[previous].z-vertices[next].z)<1e-9)throw new Error('Terrain path has a zero-length segment');
      if(vertices[next].y>vertices[previous].y+1e-7)throw new Error('Terrain path climbs uphill');
      constraints.push([previous,next]);previous=next;
    }
  }
  const segments=constraints.map(([i,j])=>({i,j,a:vertices[i],b:vertices[j]}));
  // Sweep by horizontal bounds before exact segment-intersection checks.
  segments.sort((u,v)=>Math.min(u.a.x,u.b.x)-Math.min(v.a.x,v.b.x));
  for(let i=0;i<segments.length;i++){
    const a=segments[i],maxX=Math.max(a.a.x,a.b.x);
    for(let j=i+1;j<segments.length;j++){
      const b=segments[j];if(Math.min(b.a.x,b.b.x)>maxX+1e-9)break;
      if(a.i===b.i||a.i===b.j||a.j===b.i||a.j===b.j)continue;
      if(Math.max(a.a.z,a.b.z)<Math.min(b.a.z,b.b.z)-1e-9||Math.max(b.a.z,b.b.z)<Math.min(a.a.z,a.b.z)-1e-9)continue;
      const o1=orientation(a.a,a.b,b.a),o2=orientation(a.a,a.b,b.b),o3=orientation(b.a,b.b,a.a),o4=orientation(b.a,b.b,a.b);
      const on=(p,u,v,o)=>Math.abs(o)<1e-12 && p.x>=Math.min(u.x,v.x)-1e-9 && p.x<=Math.max(u.x,v.x)+1e-9 && p.z>=Math.min(u.z,v.z)-1e-9 && p.z<=Math.max(u.z,v.z)+1e-9;
      if((o1*o2< -1e-12&&o3*o4< -1e-12)||on(b.a,a.a,a.b,o1)||on(b.b,a.a,a.b,o2)||on(a.a,b.a,b.b,o3)||on(a.b,b.a,b.b,o4))throw new Error('Terrain primary paths cross or overlap');
    }
  }
  // Coincident coordinates with different heights cannot define one surface.
  const locations=new Map();
  for(let i=0;i<vertices.length;i++){
    const p=vertices[i],key=`${p.x.toFixed(8)},${p.z.toFixed(8)}`;
    if(locations.has(key))throw new Error('Terrain contains coincident vertices');
    locations.set(key,i);
  }
  let triangles;
  try {triangles=cdt2d(vertices.map(p=>[p.x,p.z]),constraints,{exterior:true});}
  catch {throw new Error('Could not construct constrained terrain');}
  const meshEdges=new Set();
  for(const t of triangles)for(let i=0;i<3;i++)meshEdges.add([t[i],t[(i+1)%3]].sort((a,b)=>a-b).join(','));
  for(const edge of constraints)if(!meshEdges.has([...edge].sort((a,b)=>a-b).join(',')))throw new Error('Terrain lost a primary path constraint');
  return {vertices,triangles,constraints};
}
