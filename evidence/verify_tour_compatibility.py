"""Exercise the original guide-free snapshot and narrow-screen source notes."""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--origin", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
checks, errors = [], []


def check(name, condition):
    checks.append({"check": name, "passed": bool(condition)})
    assert condition, name


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


viewer = Path(__file__).resolve().parents[1] / "experiments/3d-layered"
server = ThreadingHTTPServer(
    ("127.0.0.1", 0), partial(QuietHandler, directory=str(viewer))
)
Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{server.server_port}/?example=saved")
        page.wait_for_selector('body[data-ready="true"]')
        page.locator("#start-exploring").click()
        check(
            "Saved example still selects a function",
            bool(page.locator("body").get_attribute("data-selected-node")),
        )
        check(
            "Saved example has no authored tour",
            not page.locator("#source-tour").is_visible(),
        )
        check(
            "Standalone hides unavailable themes",
            not page.locator("#map-theme").is_visible(),
        )
        check(
            "Saved example retains original 46 functions",
            page.evaluate("__debug.graph.nodes.length") == 46,
        )
        page.screenshot(path=str(args.output / "saved-example.png"))
        page.set_viewport_size({"width": 320, "height": 740})
        for project in ["portfolio", "scribblescan", "flowcode"]:
            page.goto(args.origin + "/how-it-works?project=" + project)
            page.wait_for_selector('body[data-ready="true"]')
            page.locator("#start-exploring").click()
            page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
            check(
                project + " 320px explanation visible",
                page.locator("#i-desc").is_visible(),
            )
            check(
                project + " 320px no horizontal overflow",
                page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
            )
            page.locator("#tour-next").click()
            check(
                project + " 320px can advance",
                page.locator("#tour-progress").inner_text() == "Source tour · 2 / 3",
            )
            check(
                project + " 320px notes leave legend clear",
                page.evaluate("""() =>
                document.getElementById('info').getBoundingClientRect().bottom + 4 <=
                document.getElementById('legend').getBoundingClientRect().top
            """),
            )
            page.screenshot(path=str(args.output / (project + "-320.png")))
        check("No uncaught browser errors", not errors)
        browser.close()
finally:
    server.shutdown()
    server.server_close()
(args.output / "receipt.json").write_text(
    json.dumps({"checks": checks, "errors": errors}, indent=2) + "\n"
)
print(json.dumps({"passed": len(checks), "errors": errors}))
