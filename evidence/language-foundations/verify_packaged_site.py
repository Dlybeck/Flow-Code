"""Browser acceptance for output produced by ``flowcode site``."""

from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

origin = os.environ.get("FLOWCODE_VIEWER_ORIGIN", "http://127.0.0.1:8794")
output = Path(os.environ.get("FLOWCODE_VIEWER_OUT", "/out"))
output.mkdir(parents=True, exist_ok=True)
errors: list[str] = []
external_requests: list[str] = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    )
    try:
        page = browser.new_page(viewport={"width": 1200, "height": 800})
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
            if not request.url.startswith(origin)
            else None,
        )
        page.goto(origin, wait_until="networkidle")
        page.wait_for_selector('body[data-renderer="webgl"][data-ready="true"]')
        actual = page.evaluate(
            """() => ({
              languages: [...new Set(window.__debug.graph.nodes.map(n => n.language))],
              functions: window.__debug.graph.nodes.length,
              config: JSON.parse(document.querySelector('#viewer-config').textContent),
            })"""
        )
        assert actual["languages"] == ["java"]
        assert actual["functions"] == 3
        assert actual["config"]["mapUrl"] == "graph.json"
        assert actual["config"]["projects"] == [
            {"id": "graph", "label": "golden-java"}
        ]
        assert not errors
        assert not external_requests
        result = {
            "status": "passed",
            "renderer": "webgl",
            "project": actual["config"]["projects"][0]["label"],
            "language": actual["languages"][0],
            "functions": actual["functions"],
            "map_url": actual["config"]["mapUrl"],
            "errors": errors,
            "external_requests": external_requests,
        }
    except Exception as error:
        result = {
            "status": "failed",
            "error": str(error),
            "errors": errors,
            "external_requests": external_requests,
        }
        raise
    finally:
        (output / "packaged-site.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2), flush=True)
        browser.close()
