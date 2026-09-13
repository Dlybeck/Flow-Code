"""Final rendered review of semantic data, landmarks, themes, and static serving."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

origin = "http://100.118.63.4:8097"
out = Path("/out/rendered-review")
out.mkdir(exist_ok=False)
errors, requests, checks = [], [], []


def check(name, condition):
    checks.append({"check": name, "passed": bool(condition)})
    assert condition, name


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append({"url": r.url, "method": r.method}))

    def ready():
        page.wait_for_selector('body[data-ready="true"]')
        page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    for project in ["portfolio", "flowcode", "scribblescan"]:
        for scope in ["feature", "overview"]:
            page.goto(f"{origin}/how-it-works?project={project}&scope={scope}")
            ready()
            check(project + scope + " importance height", page.evaluate("__debug.graph.nodes.every(n => __debug.currentPositions.get(n.id)[1] === n.semantic_height)"))
            check(project + scope + " visible landmarks", page.locator(".map-landmark:visible").count() > 0)
            page.screenshot(path=str(out / f"{project}-{scope}.png"))
    page.goto(origin + "/how-it-works?project=portfolio")
    ready()
    for theme in page.locator("#map-theme option").evaluate_all("xs => xs.map(x => x.value)"):
        page.set_viewport_size({"width": 1440, "height": 960})
        page.locator("#map-theme").select_option(theme)
        page.wait_for_function("id => document.body.dataset.theme === id", arg=theme)
        ready()
        page.screenshot(path=str(out / f"{theme}-desktop.png"))
        page.set_viewport_size({"width": 390, "height": 844})
        ready()
        check(theme + " phone legend", page.locator("#legend small").is_visible())
        check(theme + " phone landmarks", page.locator(".map-landmark:visible").count() > 0)
        check(theme + " phone fit", page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
        page.screenshot(path=str(out / f"{theme}-phone.png"))
    check("No page errors", not errors)
    check("Only static/local GET requests", all(r["method"] == "GET" and r["url"].startswith(origin + "/") for r in requests))
    browser.close()
(out / "receipt.json").write_text(json.dumps({"checks": checks, "errors": errors, "requests": requests}, indent=2))
print(json.dumps({"passed": len(checks), "errors": errors}))
