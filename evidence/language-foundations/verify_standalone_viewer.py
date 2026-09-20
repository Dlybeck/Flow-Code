"""Browser acceptance for independent single-language Flow-Code maps."""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ORIGIN = os.environ.get("FLOWCODE_VIEWER_ORIGIN", "http://127.0.0.1:8793")
OUT = Path(os.environ.get("FLOWCODE_VIEWER_OUT", "/out"))
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED = {
    "python": ("python", 8),
    "javascript": ("javascript", 3),
    "typescript": ("typescript", 5),
    "java": ("java", 3),
    "c": ("c", 3),
    "csharp": ("csharp", 3),
    "haskell": ("haskell", 3),
}
checks: list[dict[str, object]] = []
errors: list[str] = []
external_requests: list[str] = []


def check(name: str, condition: bool, **details: object) -> None:
    assert condition, name
    checks.append({"name": name, **details})


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    )
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        page.set_default_timeout(15_000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if not request.url.startswith(ORIGIN)
            else None,
        )
        for project, (language, count) in EXPECTED.items():
            page.goto(f"{ORIGIN}/?project={project}&scope=overview", wait_until="networkidle")
            page.wait_for_selector('body[data-renderer="webgl"][data-ready="true"]')
            actual = page.evaluate(
                """() => ({
                  count: window.__debug.graph.nodes.length,
                  languages: [...new Set(window.__debug.graph.nodes.map(n => n.language))],
                  project: document.querySelector('#project-picker').value,
                  summary: document.querySelector('#snapshot-summary').textContent,
                  points: window.__debug.scene.children.filter(x => x.userData.node).length,
                })"""
            )
            check(f"{project}: selected portable map", actual["project"] == project)
            check(
                f"{project}: expected functions render",
                actual["count"] == count and actual["points"] == count,
                functions=count,
            )
            check(f"{project}: language identity", actual["languages"] == [language])
            check(
                f"{project}: independent deterministic disclosure",
                "no generative AI is required" in actual["summary"],
            )
            page.locator("#start-exploring").click()
            check(
                f"{project}: entrypoint exploration",
                bool(page.locator("body").get_attribute("data-selected-node")),
            )
            page.locator('input[value="fan"]').check()
            page.locator('input[value="umap"]').check()
            check(
                f"{project}: 3D height remains finite",
                page.evaluate(
                    "() => window.__debug.graph.nodes.every(n => Number.isFinite(n.semantic_height))"
                ),
            )
            page.screenshot(path=str(OUT / f"{project}.png"))

        fallback = browser.new_page(viewport={"width": 390, "height": 844})
        fallback.add_init_script(
            """const original = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(type, ...args) {
              if (type.includes('webgl')) return null;
              return original.call(this, type, ...args);
            };"""
        )
        fallback.goto(f"{ORIGIN}/?project=java", wait_until="networkidle")
        fallback.wait_for_selector('body[data-renderer="canvas2d"][data-ready="true"]')
        check(
            "2D fallback remains explorable",
            fallback.locator("#function-picker option").count() == 4,
        )
        fallback.screenshot(path=str(OUT / "java-2d-phone.png"))
        fallback.close()
        check("No browser errors", not errors, errors=errors)
        check(
            "No third-party runtime requests",
            not external_requests,
            requests=external_requests,
        )
        result = {
            "status": "passed",
            "browser": "Chromium with SwiftShader WebGL2",
            "checks": checks,
            "errors": errors,
            "external_requests": external_requests,
        }
    except Exception as error:
        result = {
            "status": "failed",
            "error": str(error),
            "checks": checks,
            "errors": errors,
            "external_requests": external_requests,
        }
        raise
    finally:
        (OUT / "browser.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        browser.close()
