"""Check source-backed tours in the rendered viewer, including phone and 2D."""

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--origin", required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
checks, errors, requests = [], [], []


def check(label, condition):
    checks.append({"check": label, "passed": bool(condition)})
    assert condition, label


with sync_playwright() as p:
    browser = p.chromium.launch(
        args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 960})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append({"url": r.url, "method": r.method}))

    def ready(target=page):
        target.wait_for_selector('body[data-ready="true"]')
        target.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )

    def capture(name):
        page.screenshot(path=str(args.output / (name + ".png")))

    documents = {}
    for project in ["portfolio", "scribblescan", "flowcode"]:
        document = page.request.get(
            args.origin + f"/static/flowcode/maps/{project}.json"
        ).json()
        documents[project] = document
        guide = document["guide"]
        page.set_viewport_size({"width": 1440, "height": 960})
        page.goto(args.origin + "/how-it-works?project=" + project)
        ready()
        check(
            project + " named view",
            page.locator("#scope-picker option:checked").inner_text() == guide["title"],
        )
        check(
            project + " opening explains the feature",
            page.locator("#empty-info p").inner_text() == guide["summary"],
        )
        capture(project + "-opening")
        page.set_viewport_size({"width": 390, "height": 844})
        ready()
        check(
            project + " phone introduction visible",
            page.locator("#empty-info p").is_visible(),
        )
        capture(project + "-phone-opening")
        page.set_viewport_size({"width": 1440, "height": 960})
        page.locator("#start-exploring").click()
        for i, stop in enumerate(guide["stops"]):
            if i:
                page.locator("#tour-next").click()
            check(
                project + f" stop {i + 1} selects actual node",
                page.locator("body").get_attribute("data-selected-node")
                == stop["node"],
            )
            check(
                project + f" stop {i + 1} explanation",
                page.locator("#i-desc").inner_text() == stop["summary"],
            )
            check(
                project + f" stop {i + 1} shares selection",
                parse_qs(urlparse(page.url).query)["node"] == [stop["node"]],
            )
            check(
                project + f" stop {i + 1} progress",
                page.locator("#tour-progress").inner_text()
                == f"Source tour · {i + 1} / {len(guide['stops'])}",
            )
            if i:
                edge = next(
                    e
                    for e in document["views"]["feature"]["edges"]
                    if e["id"] == stop["via"]["edge"]
                )
                check(
                    project + f" stop {i + 1} source edge",
                    edge["from"] == guide["stops"][i - 1]["node"]
                    and edge["to"] == stop["node"],
                )
                status = "Resolved" if edge["confidence"] == "resolved" else "Inferred"
                check(
                    project + f" stop {i + 1} confidence",
                    page.locator("#tour-evidence").inner_text().startswith(status),
                )
            ready()
            check(
                project + f" stop {i + 1} labels stay separate",
                page.evaluate("""() => {
                const selected = document.getElementById('node-label');
                if (selected.hidden) return true;
                const a = selected.getBoundingClientRect();
                return [...document.querySelectorAll('.map-landmark')].filter(el => !el.hidden).every(el => {
                    const b = el.getBoundingClientRect();
                    return a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom;
                });
            }"""),
            )
            capture(project + f"-stop-{i + 1}")
        check(
            project + " final stop ends tour", page.locator("#tour-next").is_disabled()
        )
        page.locator("#tour-previous").click()
        selected = guide["stops"][-2]["node"]
        check(
            project + " previous step",
            page.locator("body").get_attribute("data-selected-node") == selected,
        )
        page.reload()
        ready()
        check(
            project + " reload restores explanation",
            page.locator("#i-qname").inner_text() == guide["stops"][-2]["title"],
        )
        page.locator('input[value="fan"]').check()
        check(
            project + " layout retains tour",
            page.locator("body").get_attribute("data-selected-node") == selected,
        )
        page.locator("#scope-picker").select_option("overview")
        page.wait_for_url("**scope=overview*")
        ready()
        check(
            project + " full map retains tour",
            page.locator("#tour-progress").inner_text() == "Source tour · 2 / 3",
        )
        guide_ids = {s["node"] for s in guide["stops"]}
        outside = next(
            n
            for n in document["views"]["overview"]["nodes"]
            if n["id"] not in guide_ids
        )
        page.locator("#function-picker").select_option(outside["id"])
        check(
            project + " free exploration retains source label",
            page.locator("#i-qname").inner_text()
            == (outside.get("displayName") or outside["label"]),
        )
        page.locator("#tour-restart").click()
        check(
            project + " return to tour",
            page.locator("body").get_attribute("data-selected-node")
            == guide["stops"][0]["node"],
        )
        page.locator("#clear-selection").click()
        check(
            project + " clear restores opening",
            page.locator("#empty-info").is_visible()
            and not page.locator("#source-tour").is_visible(),
        )

    page.goto(args.origin + "/how-it-works?project=flowcode")
    ready()
    page.locator("#start-exploring").click()
    for theme in page.locator("#map-theme option").evaluate_all(
        "xs => xs.map(x => x.value)"
    ):
        page.set_viewport_size({"width": 1440, "height": 960})
        page.locator("#map-theme").select_option(theme)
        page.wait_for_function("id => document.body.dataset.theme === id", arg=theme)
        ready()
        capture(theme + "-desktop")
        page.set_viewport_size({"width": 390, "height": 844})
        ready()
        check(
            theme + " phone fit",
            page.evaluate("document.documentElement.scrollWidth <= innerWidth"),
        )
        check(
            theme + " phone explanation visible", page.locator("#i-desc").is_visible()
        )
        check(
            theme + " phone next button reachable",
            page.locator("#tour-next").evaluate("""el => {
            const r = el.getBoundingClientRect();
            return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
        }"""),
        )
        capture(theme + "-phone")
        page.locator("#tour-next").click()
        check(
            theme + " phone advances source tour",
            page.locator("#tour-progress").inner_text() == "Source tour · 2 / 3",
        )
        page.locator("#tour-previous").click()

    fallback = browser.new_page(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    fallback.on("pageerror", lambda e: errors.append(str(e)))
    fallback.add_init_script("""const original = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            return type.includes('webgl') ? null : original.call(this, type, ...args);
        };""")
    fallback.goto(args.origin + "/how-it-works?project=scribblescan&theme=planets")
    ready(fallback)
    fallback.wait_for_selector('body[data-theme="planets"]')
    fallback.locator("#start-exploring").tap()
    fallback.locator("#tour-next").tap()
    fallback.locator("#tour-next").tap()
    check(
        "2D phone tour reaches saved demo explanation",
        "does not run fresh OCR" in fallback.locator("#i-desc").inner_text(),
    )
    check(
        "2D tour retains inferred connection",
        fallback.locator("#tour-evidence").inner_text().startswith("Inferred"),
    )
    fallback.screenshot(path=str(args.output / "fallback-phone.png"))
    check("No browser errors", not errors)
    check(
        "Browser uses local GET requests only",
        all(
            r["method"] == "GET" and r["url"].startswith(args.origin + "/")
            for r in requests
        ),
    )
    browser.close()

(args.output / "receipt.json").write_text(
    json.dumps({"checks": checks, "errors": errors, "requests": requests}, indent=2)
    + "\n"
)
print(json.dumps({"passed": len(checks), "errors": errors}))
