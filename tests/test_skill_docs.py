from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_documents_young_style_entry_contracts():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for text in (skill, readme):
        assert "--market stock --symbol" in text
        assert "--market fund --symbol" in text
        assert "确定性" in text
        assert "浏览器" in text

    assert "M1-M7" in readme
