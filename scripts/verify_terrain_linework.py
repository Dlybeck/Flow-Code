"""Compare rendered mesh quality and graph semantics, then inspect edge styles."""

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
parser.add_argument("--compare", type=Path)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
MEASURE = r"""() => {
 const v=window.__terrain3d,m=v.model,qualities=[],vertices=new Set();let decorativeLines=0;
 v.scene.traverse(o=>{
  if(o.isLineSegments&&!o.userData.from)decorativeLines++;
  if(!o.userData.terrain)return;
  const a=o.geometry.getAttribute('position');
  for(let i=0;i<a.count;i+=3){
   const p=[0,1,2].map(j=>[a.getX(i+j),a.getY(i+j),a.getZ(i+j)]);
   p.forEach(q=>vertices.add(q.join(',')));
   const u=p[1].map((x,j)=>x-p[0][j]),w=p[2].map((x,j)=>x-p[0][j]);
   const cross=[u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]];
   const area=Math.hypot(...cross)/2;
   const edges=p.reduce((sum,q,j)=>sum+q.reduce((s,x,k)=>s+(x-p[(j+1)%3][k])**2,0),0);
   qualities.push(4*Math.sqrt(3)*area/edges);
  }
 });
 qualities.sort((a,b)=>a-b);
 const graph={nodes:m.nodes.map(n=>n.id),parent:[...m.parent],heights:[...m.heights],scores:[...m.scores],positions:[...m.positions],primary:m.primaryEdges,secondary:m.secondaryEdges};
 return {triangles:qualities.length,vertices:vertices.size,slivers:qualities.filter(q=>q<.1).length,medianQuality:qualities[Math.floor(qualities.length/2)],decorativeLines,
 routeSegments:[...m.routes.values()].reduce((s,p)=>s+p.length-1,0),graph};
}"""
STYLES = r"""() => {
 const v=window.__terrain3d,result=[];
 v.scene.traverse(o=>{if(o.isLine&&o.userData.from){const d=o.userData;result.push({kind:d.kind,from:d.from,to:d.to,secondary:d.secondary,dashed:!!o.material.isLineDashedMaterial,dash:o.material.dashSize,gap:o.material.gapSize,arrow:!!d.arrow,visible:o.visible});}});
 return result;
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
    before = json.loads(args.compare.read_text()) if args.compare else None
    records = []
    for project in ["scribblescan", "chef", "fieldhouse", "redblack", "flowcode"]:
        page.select_option("#dataset", project)
        page.select_option("#content", "essential")
        page.select_option("#normalization", "siblings")
        page.select_option("#summits", "anchor")
        page.locator("#reset-overview").click()
        page.wait_for_timeout(250)
        assert "unavailable" not in page.locator("#verdict").inner_text()
        data = page.evaluate(MEASURE)
        graph = json.dumps(data.pop("graph"), sort_keys=True, separators=(",", ":"))
        data["graph_sha256"] = hashlib.sha256(graph.encode()).hexdigest()
        data["project"] = project
        if before:
            old = next(d for d in before["cases"] if d["project"] == project)
            assert data["graph_sha256"] == old["graph_sha256"], project
            assert data["routeSegments"] < old["routeSegments"], data
            assert data["slivers"] < old["slivers"], data
            assert data["decorativeLines"] == 0, data
            data["before"] = {
                k: old[k]
                for k in ["triangles", "slivers", "routeSegments", "medianQuality"]
            }
            styles = page.evaluate(STYLES)
            assert all(e.get("kind") for e in styles)
            for edge in styles:
                kind = edge["kind"]
                assert edge["dashed"] == (kind == "secondary"), edge
                assert edge["arrow"] == (kind == "secondary"), edge
                if kind == "secondary":
                    assert edge["dash"] < edge["gap"], edge
            data["styleKinds"] = sorted({e["kind"] for e in styles})
        if before:
            patterns = {
                e["kind"]: tuple(e.get(k) for k in ["dashed", "dash", "gap", "arrow"])
                for e in styles
            }
            assert len(set(patterns.values())) == 2, patterns
            assert all(
                value == patterns["primary"]
                for kind, value in patterns.items()
                if kind != "secondary"
            ), patterns
            if project == "scribblescan":
                assert set(patterns) == {
                    "primary",
                    "collapsed",
                    "secondary",
                    "grouping",
                }
            # Exercise both group and real-function selection styling without
            # changing Essential membership (UI expansion is checked separately).
            selection_ids = page.evaluate(
                """()=>{const m=window.__terrain3d.model;return [[...m.groups.keys()][0],m.nodes.find(n=>n.id!=='__project__'&&n.kind!=='supporting-group').id].filter(Boolean);}"""
            )

            def without_visibility(edges):
                return [{k: v for k, v in e.items() if k != "visible"} for e in edges]

            for selected_id in selection_ids:
                page.evaluate("id=>window.__terrain3d.select(id)", selected_id)
                selected_styles = page.evaluate(STYLES)
                assert without_visibility(selected_styles) == without_visibility(styles)
            data["styles_survive_selection"] = True
            data["two_style_patterns"] = True
            page.evaluate("window.__terrain3d.select('__project__')")
        records.append(data)
        page.locator(".stage").first.screenshot(path=str(args.out / f"{project}.png"))
    assert not errors, errors
    receipt = {"cases": records, "errors": errors}
    for name in [
        "terrain-rules-prototype.html",
        "prototype-fixtures.json",
        "dist/prototype-3d.js",
    ]:
        receipt[name + "_sha256"] = hashlib.sha256(
            page.request.get(urljoin(args.url, name)).body()
        ).hexdigest()
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(records, indent=2), flush=True)
    browser.close()
