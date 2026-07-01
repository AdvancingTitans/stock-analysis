from __future__ import annotations

from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_does_not_depend_on_young_stock_cli():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"].get("dependencies", [])
    assert not any("young-stock-cli" in item for item in dependencies)

    runtime_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "stock_analysis").rglob("*.py")
    )
    assert "young_stock" not in runtime_text
    assert "young-stock-cli" not in runtime_text
    assert "/young-stock-cli/src" not in runtime_text


def test_default_state_paths_are_stock_analysis_namespaced(monkeypatch):
    monkeypatch.delenv("STOCK_ANALYSIS_PROFILE", raising=False)
    monkeypatch.delenv("YOUNG_STOCK_PROFILE", raising=False)

    from stock_analysis import market_core
    from stock_analysis.profile import profile_path

    assert profile_path() == Path.home() / ".stock_analysis" / "profile.json"
    assert market_core.CACHE_DIR == Path.home() / ".cache" / "stock-analysis"


def test_user_facing_docs_do_not_route_to_young_stock_cli():
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "README.md",
            ROOT / "skills" / "stock-analysis" / "SKILL.md",
            ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md",
            ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md",
            ROOT / "skills" / "stock-analysis" / "agents" / "openai.yaml",
        ]
    )
    forbidden = (
        "young-stock-cli",
        "young profile",
        "~/.young_stock",
        "YOUNG_STOCK_PROFILE",
        "--lens",
    )
    for token in forbidden:
        assert token not in docs
