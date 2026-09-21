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


def assert_label_separation(page):
    page.wait_for_timeout(200)
    overlaps = page.evaluate("""() => {
      const labels=[...document.querySelectorAll('[data-kind]')].filter(e=>!e.hidden);
      const bad=[];
      labels.forEach((a,i)=>labels.slice(i+1).forEach(b=>{
        const x=a.getBoundingClientRect(), y=b.getBoundingClientRect();
        if(x.left<y.right && x.right>y.left && x.top<y.bottom && x.bottom>y.top)bad.push([a.dataset.kind,b.dataset.kind]);
      }));return bad;
    }""")
    assert not overlaps, overlaps


args = parser.parse_args()
out = args.out
out.mkdir(parents=True, exist_ok=True)
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
    page = browser.new_page(
        viewport={"width": 1500, "height": 1100}, device_scale_factor=1
    )
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(args.url, wait_until="networkidle")
    page.wait_for_function("window.__terrain3d?.model?.nodes.length > 0", timeout=60000)
    page.select_option("#content", "complete")
    page.wait_for_timeout(800)
    assert_label_separation(page)
    page.screenshot(path=str(out / "scribble-all.png"), full_page=True)
    fixture_sha = hashlib.sha256(
        page.request.get(urljoin(args.url, "prototype-fixtures.json")).body()
    ).hexdigest()
    renderer_sha = hashlib.sha256(
        page.request.get(urljoin(args.url, "dist/prototype-3d.js")).body()
    ).hexdigest()
    print("loaded", page.locator("#verdict").inner_text(), flush=True)
    landmarks = page.locator("[data-kind=entry]:visible")
    assert 1 <= landmarks.count() <= 6
    landmark_title = landmarks.first.inner_text()
    landmarks.first.click()
    assert page.locator("#node-detail strong").inner_text() in landmark_title
    records = []
    for dataset in ["scribblescan", "flowcode", "redblack", "fieldhouse", "chef"]:
        page.select_option("#dataset", dataset)
        for mode in ["siblings", "global"]:
            page.select_option("#normalization", mode)
            for summits in ["anchor", "forest"]:
                page.select_option("#summits", summits)
                record = page.evaluate(
                    """() => {const m=window.__terrain3d.model; const ridge=[]; let id=m.byId.has('__project__')?'__project__':[...m.roots].sort((a,b)=>m.byId.get(b).score-m.byId.get(a).score)[0]; while(id){ridge.push(m.byId.get(id).qname); id=[...(m.children.get(id)||[])].sort((a,b)=>m.heights.get(b)-m.heights.get(a)||a.localeCompare(b))[0];} return {ridge, nodes:m.nodes.length,orphans:m.orphans.length,violations:m.violations.length,finite:[...m.heights.values()].every(Number.isFinite),positions:[...m.positions.values()].every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y))};}"""
                )
                record.update(dataset=dataset, mode=mode, summits=summits)
                assert (
                    record["finite"]
                    and record["positions"]
                    and record["violations"] == 0
                ), record
                records.append(record)
        page.select_option("#summits", "anchor")
        assert_label_separation(page)
        page.screenshot(path=str(out / (dataset + ".png")), full_page=True)
    page.select_option("#dataset", "scribblescan")
    page.fill("#search", "handle_with_fallback")
    assert page.locator("#inventory button").count() == 1
    page.locator("#inventory button").click()
    assert "handle_with_fallback" in page.locator("#node-detail").inner_text()
    assert "Callees" in page.locator("#connections").inner_text()
    page.screenshot(path=str(out / "selected-dispatch.png"), full_page=True)
    page.fill("#search", "")
    page.select_option("#inventory-filter", "unplaced")
    expected = page.evaluate("window.__terrain3d.model.orphans.length")
    assert page.locator("#inventory button").count() == expected
    page.locator("#inventory button").first.click()
    assert "Entry path not established" in page.locator("#node-detail").inner_text()
    page.check("#all-secondary")
    page.uncheck("#all-secondary")
    page.set_viewport_size({"width": 390, "height": 844})
    assert_label_separation(page)
    page.screenshot(path=str(out / "mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # A separate local fixture exercises unknown entries and safe literal labels.
    page.set_viewport_size({"width": 1500, "height": 1100})
    fixture = {
        "title": "<img src=x onerror=alert(1)>",
        "purpose": "Independent import",
        "nodes": [
            {
                "id": "one",
                "label": "<b>literal</b>",
                "qname": "module.one",
                "score": 0.5,
            },
            {"id": "two", "label": "two", "qname": "module.two", "score": 0.2},
        ],
        "edges": [{"from": "one", "to": "two", "confidence": "resolved", "count": 1}],
        "entrypoints": [],
    }
    page.locator("#open-fixture").set_input_files(
        {
            "name": "independent.json",
            "mimeType": "application/json",
            "buffer": json.dumps(fixture).encode(),
        }
    )
    page.wait_for_function(
        "document.querySelector('#load-status').textContent.startsWith('Opened')"
    )
    assert page.locator("#project-title img").count() == 0
    for layout in ["anchor", "forest"]:
        page.select_option("#summits", layout)
        assert page.evaluate("window.__terrain3d.model.orphans.length") == 2
        assert page.evaluate(
            "[...window.__terrain3d.model.positions.values()].every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y))"
        )
    # Equal relevance keeps equal marker size/color, regardless of connectivity.
    fixture = {
        "title": "Marker proof",
        "purpose": "",
        "nodes": [
            {"id": "root", "label": "root", "qname": "root", "score": 0.1},
            {"id": "linked", "label": "linked", "qname": "linked", "score": 0.8},
            {"id": "unplaced", "label": "unplaced", "qname": "unplaced", "score": 0.8},
        ],
        "edges": [{"from": "root", "to": "linked", "confidence": "resolved"}],
        "entrypoints": ["root"],
    }
    page.locator("#open-fixture").set_input_files(
        {
            "name": "marker-proof.json",
            "mimeType": "application/json",
            "buffer": json.dumps(fixture).encode(),
        }
    )
    page.wait_for_function(
        "document.querySelector('#project-title').textContent === 'Marker proof'"
    )
    page.select_option("#normalization", "global")
    # Clear selection highlighting before comparing relevance styling.
    page.evaluate("window.__terrain3d.select(null)")
    markers = page.evaluate(
        """() => {const found={};window.__terrain3d.scene.traverse(o=>{if(['linked','unplaced'].includes(o.userData?.id))found[o.userData.id]={scale:o.scale.x,color:o.material.color.getHex(),opacity:o.material.opacity,ring:o.children.length};});return found;}"""
    )
    assert markers["linked"]["scale"] == markers["unplaced"]["scale"]
    assert markers["linked"]["color"] == markers["unplaced"]["color"]
    assert markers["unplaced"]["opacity"] == 1 and markers["unplaced"]["ring"] == 1
    assert not errors, errors
    (out / "receipt.json").write_text(
        json.dumps(
            {
                "fixture_sha256": fixture_sha,
                "renderer_sha256": renderer_sha,
                "matrix": records,
                "errors": errors,
                "inventory": True,
                "selection": True,
                "mobile": True,
                "label_separation": True,
                "landmark_click": True,
                "equal_relevance_markers": markers,
            },
            indent=2,
        )
    )
    browser.close()
