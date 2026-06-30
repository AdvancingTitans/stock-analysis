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


def test_skill_documents_user_triggered_complete_holding_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, output_discipline, portfolio_template):
        assert "用户主动" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text
        assert "只提问一次" in text
        assert "普通市场复盘报告" in text

    assert "没有主动提供持仓信息的用户不会被打扰" in skill
    assert "缺失任意一项，不得进行收益计算" in skill
    assert "没有年份" in skill and "当前年份" in skill
    assert "人民币、港币还是美元" in skill


def test_skill_documents_investment_memory_first_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "投资记忆优先" in text
        assert "~/.young_stock/profile.json" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text

    assert "默认读取投资记忆" in skill
    assert "投资记忆不存在" in skill
    assert "投资记忆有但信息不完整" in skill
    assert "保存到本地投资记忆" in skill
    assert "投资记忆已保存本地" in skill
    assert "如需清空投资记忆请反馈" in skill
    assert "除非用户明确已经清空过投资记忆" in skill

    assert "不得把本地已保存 profile 视为用户本轮主动触发持仓分析" not in skill
    assert "已保存持仓只在用户本轮主动触发持仓分析时使用" not in skill
