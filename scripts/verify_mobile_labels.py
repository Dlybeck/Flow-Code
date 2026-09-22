"""Regression check for automatic terrain labels on a phone viewport."""

import argparse

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument(
    "--url", default="http://127.0.0.1:8766/terrain-rules-prototype.html"
)
args = parser.parse_args()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--use-gl=angle",
            "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader",
        ],
    )
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(args.url, wait_until="networkidle")
    page.wait_for_function("window.__terrain3d?.model?.nodes.length>0")
    page.select_option("#dataset", "scribblescan")
    page.select_option("#content", "essential")
    page.evaluate(
        """() => {
          const view = window.__terrain3d;
          const node = view.model.nodes.find(item => item.id !== '__project__');
          view.select(node.id);
        }"""
    )
    page.wait_for_timeout(250)

    automatic = page.locator('[data-kind="entry"], [data-kind="group"]')
    visible_automatic = [
        automatic.nth(index).inner_text()
        for index in range(automatic.count())
        if automatic.nth(index).is_visible()
    ]
    assert not visible_automatic, visible_automatic
    assert page.locator('[data-kind="focus"]').is_visible()
    print("mobile automatic labels hidden; selected-node label remains visible")
    browser.close()
