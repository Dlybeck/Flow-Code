from pathlib import Path


def test_default_viewer_is_flowcode_owned(workspace_root: Path) -> None:
    html = (workspace_root / "experiments/3d-layered/index.html").read_text()
    script = (workspace_root / "experiments/3d-layered/snapshot.js").read_text()
    assert '"mapUrl":"graph.json"' in html
    assert "David Lybeck" not in html
    assert "return to the portfolio" not in script
    assert "[{id: 'graph', label: 'Codebase'}]" in script


def test_portfolio_is_an_optional_host_adapter(workspace_root: Path) -> None:
    script = (workspace_root / "experiments/3d-layered/snapshot.js").read_text()
    exporter = (workspace_root / "scripts/export_portfolio.py").read_text()
    assert "config.themeRoot || '/_theme-packs'" in script
    assert "config.returnTo || config.homeUrl || './'" in script
    assert "config.aboutUrl" in script
    assert 'href="/projects/flowcode">About Flow-Code ↗' in exporter


def test_standalone_viewer_has_no_required_remote_runtime_assets(workspace_root: Path) -> None:
    html = (workspace_root / "experiments/3d-layered/index.html").read_text()
    assert 'src="http' not in html
    assert 'href="http' not in html.replace(
        'href="https://github.com/Dlybeck/Flow-Code"', ""
    )
