from pathlib import Path


def test_console_script_entrypoint_is_declared():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[project.scripts]" in pyproject
    assert 'stock-analysis = "stock_analysis.app:run"' in pyproject
