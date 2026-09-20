import json
from pathlib import Path

import pytest

from flowcode.standalone import build_standalone_site


def _viewer(root: Path, *, built: bool = True) -> Path:
    viewer = root / "viewer"
    (viewer / "assets").mkdir(parents=True)
    (viewer / "dist").mkdir()
    (viewer / "index.html").write_text(
        '<script id="viewer-config" type="application/json">{}</script>',
        encoding="utf-8",
    )
    (viewer / "portfolio.css").write_text("body{}", encoding="utf-8")
    (viewer / "assets" / "board.svg").write_text("<svg/>", encoding="utf-8")
    if built:
        (viewer / "dist" / "app.js").write_text("export {};", encoding="utf-8")
    return viewer


def _snapshot(root: Path, project: str = "Example project") -> Path:
    path = root / "map.json"
    path.write_text(
        json.dumps({"schema_version": 2, "project": project, "views": {"overview": {}}}),
        encoding="utf-8",
    )
    return path


def test_build_standalone_site_copies_only_local_runtime_assets(tmp_path: Path) -> None:
    result = build_standalone_site(
        _snapshot(tmp_path), tmp_path / "site", viewer_root=_viewer(tmp_path)
    )

    output = tmp_path / "site"
    assert result["status"] == "built"
    assert json.loads((output / "graph.json").read_text())["project"] == "Example project"
    assert (output / "dist/app.js").read_text() == "export {};"
    assert (output / "assets/board.svg").is_file()
    html = (output / "index.html").read_text()
    assert '"label":"Example project"' in html
    assert '"mapUrl":"graph.json"' in html


def test_build_standalone_site_requires_built_viewer(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="npm ci && npm run build"):
        build_standalone_site(
            _snapshot(tmp_path), tmp_path / "site", viewer_root=_viewer(tmp_path, built=False)
        )


def test_build_standalone_site_escapes_project_label_in_script(tmp_path: Path) -> None:
    build_standalone_site(
        _snapshot(tmp_path, "Example </script><script>alert(1)</script>"),
        tmp_path / "site",
        viewer_root=_viewer(tmp_path),
    )
    html = (tmp_path / "site/index.html").read_text()
    assert "</script><script>" not in html
    assert "\\u003c/script\\u003e" in html
