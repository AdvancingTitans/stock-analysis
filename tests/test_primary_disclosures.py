import json
from pathlib import Path

from stock_analysis.primary_disclosures import extract_catalog_facts, load_issuer_primary_facts


def _catalog():
    path = Path(__file__).parents[1] / "src" / "stock_analysis" / "primary_catalog" / "600519-2025.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_extracts_numbers_and_derived_payout_without_python_issuer_logic():
    pages = {
        "annual": {
            2: "标准无保留意见的审计报告 每股派发现金红利27.993元 合计拟派发现金红利 35,032,568,759.73元",
            6: "归属于上市公司股东的净利润 82,320,067,101.68",
            9: "销售费用 7,253,499,600.68 5,639,300,059.49 28.62",
            10: (
                "茅台酒 146,499,906,480.49 9,484,757,825.54 93.53 0.39 9.50 "
                "其他系列酒 22,274,678,707.16 5,321,142,314.05 76.11 -9.76 7.11 "
                "批发代理 84,231,553,333.02 10,226,331,441.18 87.86 -12.05 0.89 "
                "直销 84,543,031,854.63 4,579,568,698.41 94.58 12.96 31.07 "
                "酒类 吨 116,123.73 85,104.14 339,977.86 11.25 2.13 9.67 "
                "筹资活动产生的现金流量净额变动原因说明：主要是本期公司回购股票"
            ),
            15: "同比新增基酒产能 1,800.00 吨 系列酒 基酒设计产能为 59,400.00 吨，同比新增基酒产能 6,940.00 吨",
            16: "生产到出厂 至少需要五年",
        }
    }
    facts = extract_catalog_facts(_catalog(), pages)
    metrics = {item["metric"]: item for items in facts.values() for item in items}

    assert metrics["direct_sales_revenue"]["value"] == 84_543_031_854.63
    assert round(metrics["shareholder_payout_ratio_pct"]["value"], 2) == 42.56
    assert metrics["annual_dividend_total"]["extraction_method"] == "official_pdf_regex"


def test_new_issuer_catalog_requires_no_python_branch(tmp_path):
    catalog = {
        "symbol": "000001", "period": "2025FY", "published_at": "2026-03-01", "source": "测试公司年报",
        "documents": {"annual": {"url": "https://example.test/report.pdf"}},
        "facts": [{"module": "C1", "metric": "direct_sales_revenue", "document": "annual", "page": 3, "pattern": "直销收入 ([\\d.]+)"}],
    }
    (tmp_path / "000001-2025.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

    facts = load_issuer_primary_facts(
        "000001", "20260302", catalog_dir=tmp_path, page_loader=lambda _url, _pages: {3: "直销收入 123.45"}
    )

    assert facts["C1"][0]["value"] == 123.45
    assert facts["C1"][0]["source"] == "测试公司年报"
