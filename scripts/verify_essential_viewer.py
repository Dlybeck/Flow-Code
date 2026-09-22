"""Essential selection, expansion, and actual rendered-surface regressions."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument(
    "--url", default="http://127.0.0.1:8766/terrain-rules-prototype.html"
)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
AUDIT = r"""() => {
 const v=window.__terrain3d,m=v.model,triangles=[],lines=[];
 v.scene.traverse(o=>{
  if(o.userData.terrain){const a=o.geometry.getAttribute('position');for(let i=0;i<a.count;i+=3)triangles.push([0,1,2].map(j=>({x:a.getX(i+j),y:a.getY(i+j),z:a.getZ(i+j)})));}
  if(o.isLine&&o.userData.from&&!o.userData.secondary){const a=o.geometry.getAttribute('position');lines.push({from:o.userData.from,to:o.userData.to,points:Array.from({length:a.count},(_,i)=>({x:a.getX(i),y:a.getY(i)-.42,z:a.getZ(i)}))});}
 });
 const bins=new Map(),step=2;
 for(const t of triangles){const xs=t.map(p=>p.x),zs=t.map(p=>p.z);
  for(let x=Math.floor(Math.min(...xs)/step);x<=Math.floor(Math.max(...xs)/step);x++)for(let z=Math.floor(Math.min(...zs)/step);z<=Math.floor(Math.max(...zs)/step);z++){
   const k=`${x},${z}`;if(!bins.has(k))bins.set(k,[]);bins.get(k).push(t);
  }
 }
 function surface(x,z){let result=null;
  for(const [a,b,c] of bins.get(`${Math.floor(x/step)},${Math.floor(z/step)}`)||[]){
   const det=(b.z-c.z)*(a.x-c.x)+(c.x-b.x)*(a.z-c.z);if(Math.abs(det)<1e-14)continue;
   const u=((b.z-c.z)*(x-c.x)+(c.x-b.x)*(z-c.z))/det,w=((c.z-a.z)*(x-c.x)+(a.x-c.x)*(z-c.z))/det,t=1-u-w;
   if(u>=-1e-9&&w>=-1e-9&&t>=-1e-9){const y=u*a.y+w*b.y+t*c.y;result=result===null?y:Math.max(result,y);}
  }return result;
 }
 let samples=0,maxRise=0,maxMismatch=0,missing=0;
 for(const line of lines){let last=null;const points=[];
  line.points.forEach((a,i)=>{points.push(a);const b=line.points[i+1];if(b)points.push({x:(a.x+b.x)/2,y:(a.y+b.y)/2,z:(a.z+b.z)/2});});
  for(const p of points){const y=surface(p.x,p.z);if(y===null){missing++;continue;}samples++;maxMismatch=Math.max(maxMismatch,Math.abs(y-p.y));if(last!==null)maxRise=Math.max(maxRise,y-last);last=y;}
 }
 const rect=v.renderer.domElement.getBoundingClientRect(),topCut=Math.max(...m.heights.values())-(Math.max(...m.heights.values())-Math.min(...m.heights.values()))*.2,markers=[];
 v.scene.traverse(o=>{const id=o.userData?.id;if(!id||id==='__project__'||!o.visible||m.orphans.includes(id)||m.heights.get(id)<topCut)return;const p=o.position.clone().project(v.camera);if(Math.abs(p.x)<=1&&Math.abs(p.y)<=1)markers.push({x:p.x*rect.width/2,y:p.y*rect.height/2});});
 const crowded=markers.filter((a,i)=>markers.some((b,j)=>i!==j&&Math.hypot(a.x-b.x,a.y-b.y)<10)).length;
 const full=m.full||m, originals=m.nodes.filter(n=>n.id!=='__project__');
 const unchanged=originals.every(n=>m.heights.get(n.id)===full.heights.get(n.id)&&m.scores.get(n.id)===full.scores.get(n.id));
 const realMarkers=m.nodes.every(n=>n.id==='__project__'||full.byId.has(n.id));
 return {summitMarkers:markers.length,crowdedSummitMarkers:crowded,items:m.nodes.length-Number(m.byId.has('__project__')),branches:(m.children.get('__project__')||m.roots).length,condensed:m.primaryEdges.filter(e=>e.summarized).length,realMarkers,lines:lines.length,samples,maxRise,maxMismatch,missing,unchanged,
  inventory:full.nodes.length-Number(full.byId.has('__project__')),anchors:[...(m.anchors||[])].map(id=>m.byId.get(id)?.qname),unknown:(m.unknownHighlights||[]).map(n=>n.qname)};
}"""
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
        ],
    )
    page = browser.new_page(viewport={"width": 1500, "height": 1100})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(args.url, wait_until="networkidle")
    page.wait_for_function("window.__terrain3d?.model?.nodes.length>0")
    records = []

    def audit(label):
        assert "unavailable" not in page.locator("#verdict").inner_text(), page.locator(
            "#verdict"
        ).inner_text()
        d = page.evaluate(AUDIT)
        d["case"] = label
        assert (
            not d["missing"]
            and d["maxRise"] < 0.0002
            and d["maxMismatch"] < 0.0002
            and d["unchanged"]
            and d["realMarkers"]
        ), d
        records.append(d)
        return d

    for project in ["scribblescan", "chef", "fieldhouse", "redblack", "flowcode"]:
        page.select_option("#dataset", project)
        for content in ["essential", "complete"]:
            page.select_option("#content", content)
            for mode in ["siblings", "global"]:
                page.select_option("#normalization", mode)
                for summits in ["anchor", "forest"]:
                    page.select_option("#summits", summits)
                    d = audit(f"{project}/{content}/{mode}/{summits}")
                    if (
                        project == "scribblescan"
                        and content == "essential"
                        and mode == "siblings"
                        and summits == "anchor"
                    ):
                        assert (
                            d["crowdedSummitMarkers"] / max(1, d["summitMarkers"]) <= 0.2
                        ), d
                    if content == "essential":
                        assert d["items"] <= 40 and d["branches"] <= 6, d
            if content == "essential":
                page.select_option("#summits", "anchor")
                page.wait_for_timeout(200)
                page.locator(".stage").first.screenshot(
                    path=str(args.out / f"{project}.png")
                )
        print(project, "surface cases passed", flush=True)
    page.select_option("#dataset", "scribblescan")
    page.select_option("#content", "essential")
    page.select_option("#normalization", "siblings")
    page.select_option("#summits", "anchor")
    condensed = page.evaluate(
        """()=>{const m=window.__terrain3d.model;const e=m.primaryEdges.find(e=>e.summarized&&e.representedPath?.length>2);return e&&{target:e.to,path:e.representedPath,qname:m.byId.get(e.to).qname};}"""
    )
    assert condensed
    assert page.evaluate(
        "ids=>ids.slice(1,-1).some(id=>!window.__terrain3d.model.byId.has(id))",
        condensed["path"],
    )
    page.fill("#search", condensed["qname"])
    page.locator(f'#inventory button[data-node-id="{condensed["target"]}"]').click()
    audit("condensed path reveal")
    assert page.evaluate(
        "ids=>ids.every(id=>window.__terrain3d.model.byId.has(id))", condensed["path"]
    )
    page.locator("#reset-overview").click()
    audit("reset")
    assert page.evaluate("window.__terrain3d.model.nodes.length-1") <= 40
    hidden = page.evaluate(
        """()=>{const m=window.__terrain3d.model;return m.full.nodes.find(n=>!m.byId.has(n.id)&&!m.full.orphans.includes(n.id)&&n.id!=='__project__');}"""
    )
    page.fill("#search", hidden["qname"])
    page.locator(f'#inventory button[data-node-id="{hidden["id"]}"]').click()
    audit("search reveal")
    assert page.evaluate("id=>window.__terrain3d.model.byId.has(id)", hidden["id"])
    page.fill("#search", "")
    page.locator("#unknown-functions summary").click()
    page.locator("#unknown-list button").first.click()
    audit("unknown reveal")
    assert "Entry path not established" in page.locator("#node-detail").inner_text()
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(200)
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.screenshot(path=str(args.out / "mobile.png"), full_page=True)
    # No-entry and tiny fixtures must remain valid in both content and summit modes.
    fixture = {
        "title": "No entries",
        "purpose": "",
        "nodes": [
            {"id": "one", "label": "one", "qname": "one", "score": 0.8},
            {"id": "two", "label": "two", "qname": "two", "score": 0.2},
        ],
        "edges": [{"from": "one", "to": "two", "confidence": "resolved"}],
        "entrypoints": [],
    }
    page.locator("#open-fixture").set_input_files(
        {
            "name": "empty.json",
            "mimeType": "application/json",
            "buffer": json.dumps(fixture).encode(),
        }
    )
    page.wait_for_function(
        "document.querySelector('#project-title').textContent==='No entries'"
    )
    for content in ["essential", "complete"]:
        page.select_option("#content", content)
        for summits in ["anchor", "forest"]:
            page.select_option("#summits", summits)
            audit(f"no-entry/{content}/{summits}")
    page.select_option("#content", "essential")
    page.fill("#search", "")
    for node_id in ["one", "two"]:
        page.locator(f'#inventory button[data-node-id="{node_id}"]').click()
    audit("unplaced call reveal")
    assert page.evaluate(
        "window.__terrain3d.model.secondaryEdges.some(e=>e.from==='one'&&e.to==='two')"
    )
    assert page.evaluate("!window.__terrain3d.model.parent.has('two')")
    assert not errors, errors
    receipt = {
        "cases": records,
        "errors": errors,
        "condensed_path_reveal": True,
        "search_reveal": True,
        "unknown_reveal": True,
        "mobile": True,
    }
    for name in ["prototype-fixtures.json", "dist/prototype-3d.js"]:
        receipt[name + "_sha256"] = hashlib.sha256(
            page.request.get(urljoin(args.url, name)).body()
        ).hexdigest()
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    browser.close()
