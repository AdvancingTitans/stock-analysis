import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert match
    return match.group(1)


def test_release_version_metadata_stays_in_sync():
    version = _project_version()
    init_file = (ROOT / "src" / "stock_analysis" / "__init__.py").read_text(encoding="utf-8")
    futu_public = (ROOT / "src" / "stock_analysis" / "futu_public.py").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f'__version__ = "{version}"' in init_file
    assert f"stock-analysis/{version} (Skill)" in futu_public
    assert f"当前 CLI 版本为 `{version}`" in readme


def test_changelog_top_entry_matches_latest_project_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = re.findall(r"^## v(\d+\.\d+\.\d+) - ", changelog, re.MULTILINE)
    assert versions
    latest = max(tuple(int(part) for part in version.split(".")) for version in versions)

    assert versions[0] == _project_version()
    assert tuple(int(part) for part in versions[0].split(".")) == latest


def test_package_does_not_require_young_stock_cli_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "young-stock-cli" not in pyproject


def test_skill_documents_stock_analysis_entry_contracts():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for text in (skill, readme):
        assert "--market stock --symbol" in text
        assert "--market fund --symbol" in text
        assert "确定性" in text
        assert "浏览器" in text

    assert "不要求用户安装任何外部行情 CLI" in readme
    assert "M1-M6" in readme
    assert "内置 lens 与 committee 边界" in readme


def test_skill_documents_lens_engine_natural_language_committee_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for text in (skill, readme):
        assert "默认使用 committee 模式" in text
        assert "LensEngine 是报告生成的核心编排器" in text
        assert "用巴菲特模式分析" in text
        assert "用 adversarial 模式让巴菲特和芒格辩论" in text
        assert "m1/m6 综合深度分析" in text
        assert "社区情绪分析" in text
        assert "committee 失败时降级为 single" in text


def test_skill_documents_user_triggered_complete_holding_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, output_discipline, portfolio_template):
        assert "用户要求持仓分析" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text
        assert "只提问一次" in text
        assert "普通市场复盘报告" in text

    assert "没有主动要求持仓分析的用户不会被打扰" in skill
    assert "缺失任意一项，不得进行收益计算" in skill
    assert "没有年份" in skill and "当前年份" in skill
    assert "人民币、港币还是美元" in skill


def test_skill_documents_explicit_investment_memory_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "投资记忆" in text
        assert "~/.stock_analysis/profile.json" in text
        assert "STOCK_ANALYSIS_PROFILE" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text

    assert "持仓相关请求优先读取" in skill
    assert "投资记忆不存在" in skill
    assert "等待用户交互输入" in skill
    assert "投资记忆有但信息不完整" in skill
    assert "保存到本地投资记忆" in skill
    assert "投资记忆已保存本地" in skill
    assert "如需清空投资记忆请反馈" in skill
    assert "普通行情复盘不得因为本机存在投资记忆而自动插入持仓绩效" in skill

    assert "~/.young_stock/profile.json" not in skill
    assert "YOUNG_STOCK_PROFILE" not in skill


def test_skill_documents_new_user_holdings_override_saved_memory_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "新提供的信息与之前保存的投资记忆不一致" in text
        assert "优先以用户新提供的信息为准" in text
        assert "覆盖写入投资记忆" in text
        assert "确认信息完整性后" in text

    assert "不完整的新信息不得覆盖已有完整投资记忆" in skill


def test_skill_documents_builtin_investor_lens_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    expected_lenses = (
        "buffett",
        "munger",
        "graham",
        "klarman",
        "lynch",
        "o_neil",
        "wood",
        "dalio",
        "soros",
        "livermore",
        "minervini",
        "simons",
        "duan_yongping",
        "zhang_kun",
        "feng_liu",
    )
    for lens in expected_lenses:
        assert lens in skill

    for text in (skill, readme, output_discipline, portfolio_template):
        assert "用户明确提出想用哪位投资专家的风格" in text
        assert "完全以相关专家的视角输出报告" in text
        assert "不得只在结尾追加专家点评" in text
        assert "单专家视角" in text
        assert "多专家" in text
        assert "不得模仿身份声明或虚构专家发言" in text

    assert "15 个 stock-analysis 内置投资专家 lens" in skill
    assert "config/lenses/*.json" in skill
    assert "scripts/lens_registry.py" in skill
    assert "不要求用户安装任何外部行情 CLI" in skill
    assert "专家名称、英文名、中文名、别名或 lens id" in skill
    assert "## {专家中文名}持仓建议与风险提示" in skill
    assert "交易计划草案" in skill
    assert "组合经理最终意见" in skill
