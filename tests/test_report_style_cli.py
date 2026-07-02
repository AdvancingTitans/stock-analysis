from stock_analysis.app import build_parser
from stock_analysis.reporting import render_report, render_report_with_metadata


def test_parser_exposes_report_style_flag():
    parser = build_parser()
    args = parser.parse_args(["--market", "daily", "--report-style", "classic"])
    assert args.report_style == "classic"


def test_render_report_alias_uses_committee_structure():
    assert render_report.__doc__ is not None
    assert "committee" in render_report.__doc__.lower()
    assert render_report_with_metadata is not None