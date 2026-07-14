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
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")

    assert f'__version__ = "{version}"' in init_file
    assert f"stock-analysis/{version} (Skill)" in futu_public
    assert f"Current CLI version: `{version}`" in readme
    assert f"当前 CLI 版本为 `{version}`" in zh_readme
    assert f'version: "{version}"' in skill
    assert '<a href="./README.zh-CN.md">简体中文</a>' in readme
    assert '<a href="./README.md">English</a>' in zh_readme


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
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    for text in (skill, zh_readme):
        assert "--market stock --symbol" in text
        assert "--market fund --symbol" in text
        assert "确定性" in text
        assert "浏览器" in text

    assert "不要求用户安装任何外部行情 CLI" in zh_readme
    assert "M1-M6" in zh_readme
    assert "内置 lens 与 committee 边界" in zh_readme


def test_readmes_list_both_accepted_awesome_quant_repositories_and_agent_entrypoints():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    badge = (
        '<a href="https://github.com/leoncuhk/awesome-quant-ai"><img '
        'alt="Listed in leoncuhk/awesome-quant-ai" '
        'src="https://img.shields.io/badge/listed%20in-leoncuhk%2Fawesome--quant--ai-2ea44f"></a>'
    )

    for text in (readme, zh_readme):
        assert badge in text
        assert "https://github.com/thuquant/awesome-quant" in text
        assert "https://github.com/leoncuhk/awesome-quant-ai" in text

    assert "Intent matching happens in the host Agent" in readme
    assert "意图识别发生在宿主 Agent" in zh_readme


def test_skill_documents_lens_engine_natural_language_committee_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")

    for text in (skill, zh_readme):
        assert "默认使用 committee 模式" in text
        assert "LensEngine 是报告生成的核心编排器" in text
        assert "用巴菲特模式分析" in text
        assert "用 adversarial 模式让巴菲特和芒格辩论" in text
        assert "M1-M6" in text or "m1/m6 综合深度分析" in text
        assert "committee 失败时降级为 single" in text


def test_skill_documents_fixed_committee_report_structure_and_advice_sections():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")

    for text in (skill, zh_readme, output_discipline):
        assert "执行摘要" in text
        assert "大盘指数概览" in text
        assert "六模块深度复盘" in text
        assert "现状总结" in text
        assert "基准跑赢/跑输" in text
        assert "条件化仓位动作" in text
        assert "下一交易日观察清单" in text
        assert "风险提示" in text

    assert "证据暂缺" in skill
    assert "证据暂缺" in zh_readme
    assert "不得直接跳过大盘或六模块" in output_discipline
    assert "证据附录不进入早盘、盘中、午间或盘后正文" in zh_readme
    assert "正文不输出证据附录" in skill
    assert "不得输出“证据附录”章节" in output_discipline


def test_skill_documents_public_fund_profile_source_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    data_source_strategy = (
        ROOT / "skills" / "stock-analysis" / "references" / "data-source-strategy.md"
    ).read_text(encoding="utf-8")

    for text in (skill, zh_readme, data_source_strategy):
        assert "pingzhongdata" in text
        assert "长期业绩" in text
        assert "前端费率" in text
        assert "基金经理" in text
        assert "无需 API key" in text or "不依赖登录或 API key" in text

    assert "EASTMONEY_APIKEY" in data_source_strategy
    assert "不作为本技能默认数据源" in data_source_strategy


def test_skill_documents_user_triggered_complete_holding_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, output_discipline, portfolio_template):
        assert "用户主动提供持仓" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text
        assert "只提问一次" in text
        assert "普通市场复盘报告" in text

    assert "用户本次输入的完整持仓" in skill
    assert "不得回退使用旧投资记忆" in skill
    assert "缺失任意一项，不得进行收益计算" in skill
    assert "没有年份" in skill and "当前年份" in skill
    assert "人民币、港币还是美元" in skill


def test_skill_documents_explicit_investment_memory_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, zh_readme, output_discipline, portfolio_template):
        assert "投资记忆" in text
        assert "~/.stock_analysis/profile.json" in text
        assert "STOCK_ANALYSIS_PROFILE" in text
        assert "股票代码、买入日期、买入数量或买入金额" in text

    assert "trading 入口" in skill
    assert "用户完整持仓输入" in output_discipline
    assert "投资记忆不存在或不完整" in skill
    assert "等待用户交互输入" in skill
    assert "用户主动提供持仓相关内容但缺失核心字段" in skill
    assert "保存到本地投资记忆" in skill
    assert "投资记忆已保存本地" in skill
    assert "如需清空投资记忆请反馈" in skill
    assert "用户没有提供持仓时，才读取本地投资记忆" in skill

    assert "~/.young_stock/profile.json" not in skill
    assert "YOUNG_STOCK_PROFILE" not in skill


def test_skill_documents_new_user_holdings_override_saved_memory_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    output_discipline = (
        ROOT / "skills" / "stock-analysis" / "references" / "output_discipline.md"
    ).read_text(encoding="utf-8")
    portfolio_template = (
        ROOT / "skills" / "stock-analysis" / "references" / "template" / "portfolio-template.md"
    ).read_text(encoding="utf-8")

    for text in (skill, zh_readme, output_discipline, portfolio_template):
        assert "新提供的信息与之前保存的投资记忆不一致" in text
        assert "优先以用户新提供的信息为准" in text
        assert "覆盖写入投资记忆" in text
        assert "确认信息完整性后" in text

    assert "不完整的新信息不得覆盖已有完整投资记忆" in skill


def test_skill_documents_builtin_investor_lens_contract():
    skill = (ROOT / "skills" / "stock-analysis" / "SKILL.md").read_text(encoding="utf-8")
    zh_readme = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
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

    for text in (skill, zh_readme, output_discipline, portfolio_template):
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
