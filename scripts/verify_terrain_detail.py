"""Browser regression for crowded overview markers and lossless detail controls."""

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

measure = """() => {
  const {scene,camera,model:m,renderer}=window.__terrain3d;
  const rect=renderer.domElement.getBoundingClientRect(), points=[], enabled=[];
  const cutoff=Math.max(...m.heights.values())-(Math.max(...m.heights.values())-Math.min(...m.heights.values()))*.2;
  scene.traverse(o=>{if(!o.userData?.id||!o.visible)return;enabled.push(o.userData.id);
    const p=o.position.clone().project(camera);
    if(o.userData.id==='__project__'||Math.abs(p.x)>1||Math.abs(p.y)>1||Math.abs(p.z)>1)return;
    points.push({id:o.userData.id,x:(p.x+1)*rect.width/2,y:(1-p.y)*rect.height/2,top:!m.orphans.includes(o.userData.id)&&m.heights.get(o.userData.id)>=cutoff});
  });
  const top=points.filter(p=>p.top);
  const close=top.filter((a,i)=>top.some((b,j)=>i!==j&&Math.hypot(a.x-b.x,a.y-b.y)<10));
  return {total:m.nodes.filter(n=>n.id!=='__project__').length,enabled,inView:points.length,top:top.length,crowded:close.length,
    graph:JSON.stringify({heights:[...m.heights],positions:[...m.positions],parent:[...m.parent],edges:m.fixture.edges})};
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
    page.select_option("#content", "complete")
    results = []
    for dataset in ["scribblescan", "chef", "fieldhouse", "redblack", "flowcode"]:
        page.select_option("#dataset", dataset)
        page.select_option("#detail", "overview")
        page.wait_for_timeout(300)
        overview = page.evaluate(measure)
        assert overview["crowded"] == 0, overview
        page.screenshot(path=str(args.out / f"{dataset}-overview.png"), full_page=True)
        page.select_option("#detail", "all")
        page.wait_for_timeout(200)
        full = page.evaluate(measure)
        assert len(full["enabled"]) == full["total"] + 1
        assert full["graph"] == overview["graph"]
        if dataset == "scribblescan":
            assert len(full["enabled"]) > len(overview["enabled"])
            page.screenshot(path=str(args.out / "scribblescan-all.png"), full_page=True)
        page.select_option("#detail", "overview")
        page.wait_for_timeout(200)
        if dataset == "scribblescan":
            # Zoom the summit using the same camera/controls as interactive zoom.
            page.evaluate(
                """() => {const v=window.__terrain3d;v.focus('__project__');v.camera.position.sub(v.controls.target).multiplyScalar(.45).add(v.controls.target);v.controls.update();}"""
            )
            page.wait_for_timeout(250)
            zoomed = page.evaluate(measure)
            revealed = set(zoomed["enabled"]) - set(overview["enabled"])
            assert revealed, "Zoom must reveal previously hidden markers"
            page.screenshot(
                path=str(args.out / "scribblescan-zoom.png"), full_page=True
            )
            page.evaluate("window.__terrain3d.reset()")
            page.wait_for_timeout(250)
            selected = page.evaluate("""() => {
              const v=window.__terrain3d, hidden=[];
              v.scene.traverse(o=>{if(o.userData?.id&&!o.visible&&v.model.parent.has(o.userData.id)&&!v.model.orphans.includes(o.userData.id))hidden.push(o.userData.id);});
              const id=hidden.sort()[0];v.select(id);return id;
            }""")
            assert selected
            page.wait_for_timeout(200)
            assert page.evaluate(
                """id => {
              const v=window.__terrain3d, needed=new Set([id]);let cursor=id;
              while(v.model.parent.has(cursor)){cursor=v.model.parent.get(cursor);needed.add(cursor);}
              for(const e of v.model.fixture.edges)if(e.from===id||e.to===id){needed.add(e.from);needed.add(e.to);}
              const shown=new Set();v.scene.traverse(o=>{if(o.visible&&o.userData?.id)shown.add(o.userData.id);});
              return [...needed].every(n=>shown.has(n));
            }""",
                selected,
            ), "Selection must expose the complete path and direct callers/callees"
            page.check("#all-secondary")
            page.wait_for_timeout(200)
            assert page.evaluate(
                """() => {const v=window.__terrain3d, shown=new Set();v.scene.traverse(o=>{if(o.visible&&o.userData?.id)shown.add(o.userData.id);});return v.model.secondaryEdges.every(e=>shown.has(e.from)&&shown.has(e.to));}"""
            )
            page.uncheck("#all-secondary")
        results.append(
            {
                "dataset": dataset,
                "functions": overview["total"],
                "overview_markers_in_view": overview["inView"],
                "overview_summit_markers": overview["top"],
                "overview_crowded": overview["crowded"],
                "all_summit_markers": full["top"],
                "all_crowded": full["crowded"],
                "unchanged_geometry_and_calls": True,
            }
        )
    assert not errors, errors
    receipt = {
        "cases": results,
        "zoom_reveals_hidden": True,
        "selected_path_and_neighbors": True,
        "secondary_endpoints": True,
        "errors": errors,
    }
    for name in ["prototype-fixtures.json", "dist/prototype-3d.js"]:
        receipt[name + "_sha256"] = hashlib.sha256(
            page.request.get(urljoin(args.url, name)).body()
        ).hexdigest()
    (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    browser.close()
