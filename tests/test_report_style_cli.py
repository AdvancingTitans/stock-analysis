from stock_analysis.app import build_parser


def test_parser_exposes_report_style_flag():
    parser = build_parser()
    args = parser.parse_args(["--market", "daily", "--report-style", "classic"])
    assert args.report_style == "classic"