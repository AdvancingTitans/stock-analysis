#!/usr/bin/env python3
"""stock-analysis skill wrapper around young-stock-cli core modules.

Usage examples:
  python scripts/aftermarket.py --market daily
  python scripts/aftermarket.py --market global
  python scripts/aftermarket.py --market stock --stock 600519
  python scripts/aftermarket.py --market fund --fund 161725
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _load_core():
    try:
        from young_stock import _core
    except ModuleNotFoundError:
        print(
            "错误: stock-analysis v3.6+ 依赖 young-stock-cli 核心包。\n"
            "请先运行: python -m pip install -U young-stock-cli",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    return _core


def _profile_path() -> Path:
    override = os.environ.get("YOUNG_STOCK_PROFILE")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".young_stock" / "profile.json"


def _load_watchlist() -> dict[str, list[str]]:
    path = _profile_path()
    if not path.exists():
        return {"stocks": [], "funds": []}
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"stocks": [], "funds": []}
    return {
        "stocks": [str(v) for v in data.get("stocks", []) if str(v).strip()],
        "funds": [str(v) for v in data.get("funds", []) if str(v).strip()],
    }


def _print_first_use_guide() -> None:
    print("# 每日行情日报\n")
    print("尚未设置投资记忆。请先让用户给出关注的股票、ETF 或基金，然后保存到 CLI profile：")
    print("  young profile add-stock 600519")
    print("  young profile add-stock 0700.HK")
    print("  young profile add-fund 161725")
    print()
    print(f"当前配置路径: {_profile_path()}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="stock-analysis wrapper for young-stock-cli")
    parser.add_argument("date", nargs="?", help="Trade date YYYYMMDD")
    parser.add_argument("--market", default="daily", choices=["daily", "a", "hk", "us", "global", "stock", "news", "fund"])
    parser.add_argument("--stock", "--symbol", dest="stock")
    parser.add_argument("--fund", dest="fund")
    parser.add_argument("--no-cache", "--refresh", dest="no_cache", action="store_true")
    parser.add_argument("--no-news", action="store_true")
    parser.add_argument("--format", dest="report_format", default="full", choices=["full", "summary", "key-points"])
    parser.add_argument("--only", default=None)
    parser.add_argument("--order", default=None)
    parser.add_argument("--quick", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    core = _load_core()
    if args.no_cache:
        core.NO_CACHE = True
    core.cache_clear_old(days=7)
    date_str = args.date or core.nearest_trade_date()
    include_news = not args.no_news

    if args.market == "daily":
        watchlist = _load_watchlist()
        if not watchlist.get("stocks") and not watchlist.get("funds"):
            _print_first_use_guide()
            return 0
        core.run_daily_report(
            date_str,
            watchlist,
            include_news=include_news,
            report_format=args.report_format,
            only=args.only,
            order=args.order,
            quick=args.quick,
        )
    elif args.market == "a":
        core.run_a_share(date_str, include_news=include_news)
    elif args.market == "hk":
        core.run_hk_market(date_str, include_news=include_news)
    elif args.market == "us":
        core.run_us_market(date_str, include_news=include_news)
    elif args.market == "global":
        core.run_global_market(date_str)
    elif args.market == "stock":
        if not args.stock:
            print("错误: --market stock 需要配合 --stock 600519 使用", file=sys.stderr)
            return 2
        core.run_stock_quote(args.stock, date_str, include_news=include_news)
    elif args.market == "news":
        if not args.stock:
            print("错误: --market news 需要配合 --stock 3690.HK 使用", file=sys.stderr)
            return 2
        core.run_stock_news(args.stock, date_str)
    elif args.market == "fund":
        fund_code = args.fund or args.stock
        if not fund_code:
            print("错误: --market fund 需要配合 --fund 161725 使用", file=sys.stderr)
            return 2
        core.run_fund_report(fund_code, date_str, include_news=include_news)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
