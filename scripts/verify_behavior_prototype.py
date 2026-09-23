"""Rendered acceptance for the recursive behavior prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", default="http://127.0.0.1:8766/behavior-prototype.html"
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_function(
            "window.__behaviorPrototype?.model?.behaviors.length >= 0"
        )
        records = []
        projects = page.locator("#project option").evaluate_all(
            "options => options.map(option => option.value)"
        )
        for project in projects:
            page.select_option("#project", project)
            overview = page.evaluate(
                """() => ({
                  project: window.__behaviorPrototype.projectId,
                  total: window.__behaviorPrototype.model.behaviors.length,
                  primary: document.querySelectorAll('.behavior-card').length,
                  accounted: window.__behaviorPrototype.model.coverage.accounted_function_ids.length,
                  layers: Object.keys(window.__behaviorPrototype.model.layers).length,
                })"""
            )
            assert overview["primary"] <= 6
            assert overview["accounted"] == overview["layers"]
            page.locator("#all-code").click()
            assert page.locator("#code-list .code-row").count() == overview["accounted"]
            page.locator("#close-code").click()
            page.screenshot(
                path=str(args.out / f"{project}-overview.png"), full_page=True
            )
            if project == "scribblescan":
                opened = page.evaluate(
                    """() => {
                      const card = [...document.querySelectorAll('.behavior-card')]
                        .find(row => row.querySelector('.behavior-start')?.textContent.trim() === 'Digitize images');
                      card?.click();
                      return Boolean(card);
                    }"""
                )
                assert opened
                json_outcomes = page.evaluate(
                    """() => window.__behaviorPrototype.layer.nodes
                      .filter(node => node.kind === 'leaf' && node.label === 'Return JSONResponse')
                      .map(node => ({count: node.exit_count, sources: node.source_refs.length}))"""
                )
                assert json_outcomes == [{"count": 11, "sources": 11}]
                assert page.locator(".map-node.leaf", has_text="11 VARIANTS").count() == 1
                page.screenshot(
                    path=str(args.out / "scribblescan-digitize-images.png"),
                    full_page=True,
                )
                page.locator("#crumbs button").first.click()
            if overview["primary"]:
                page.locator(".behavior-card").first.click()
                page.wait_for_selector(".map-node.root")
                base = page.evaluate(
                    """() => ({
                      layer: window.__behaviorPrototype.layerId,
                      ids: [...document.querySelectorAll('.map-node')].map(node => node.dataset.nodeId),
                      edges: [...document.querySelectorAll('.graph-edge')].map(edge => [edge.dataset.from, edge.dataset.to]),
                      expectedEdges: window.__behaviorPrototype.layer.edges.map(edge => [edge.from, edge.to]),
                      backed: window.__behaviorPrototype.layer.nodes.every(node => node.source_refs?.length),
                    })"""
                )
                assert base["backed"]
                assert base["edges"] == base["expectedEdges"]
                page.locator("[data-view=mountain]").click()
                mountain = page.evaluate(
                    """() => ({layer:window.__behaviorPrototype.layerId,
                    ids:[...document.querySelectorAll('.map-node')].map(node=>node.dataset.nodeId),
                    edges:[...document.querySelectorAll('.graph-edge')].map(edge=>[edge.dataset.from,edge.dataset.to])})"""
                )
                assert mountain["layer"] == base["layer"]
                assert mountain["ids"] == base["ids"]
                assert mountain["edges"] == base["expectedEdges"]
                page.screenshot(
                    path=str(args.out / f"{project}-mountain.png"), full_page=True
                )
                page.locator("[data-view=flow]").click()
                if page.locator(".map-node.seed").count():
                    old_layer = page.evaluate("window.__behaviorPrototype.layerId")
                    page.locator(".map-node.seed").first.click()
                    assert (
                        page.evaluate("window.__behaviorPrototype.layerId") != old_layer
                    )
                    assert page.locator("#crumbs button").count() >= 3
            page.screenshot(path=str(args.out / f"{project}.png"), full_page=True)
            records.append(overview)
        page.set_viewport_size({"width": 390, "height": 844})
        page.select_option("#project", projects[0])
        if page.locator(".behavior-card").count():
            page.locator(".behavior-card").first.click()
        page.screenshot(path=str(args.out / "mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        receipt = {"projects": records, "mobile": True, "errors": errors}
        (args.out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        browser.close()


if __name__ == "__main__":
    main()
