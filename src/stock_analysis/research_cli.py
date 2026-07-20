"""CLI orchestration for stock, fund, thesis, and recoverable research commands."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ResearchCommandServices:
    build_company_evidence: Callable[..., dict[str, Any]]
    build_fund_evidence: Callable[..., dict[str, Any]]
    build_company_workspace: Callable[..., tuple[dict[str, Any], Path]]
    build_fund_workspace: Callable[..., tuple[dict[str, Any], Path]]
    render_stock_review: Callable[[dict[str, Any]], str]
    render_earnings_review: Callable[[dict[str, Any]], str]
    render_price_move: Callable[[dict[str, Any]], str]
    create_thesis: Callable[..., tuple[dict[str, Any], Path]]
    review_thesis: Callable[..., tuple[dict[str, Any] | None, Path, list[str]]]
    render_thesis_create: Callable[[dict[str, Any], Path], str]
    render_thesis_review: Callable[[dict[str, Any] | None, Path, list[str]], str]
    load_reached_primary_evidence: Callable[..., dict[str, list[dict[str, Any]]]]


def _load_expectations(args: argparse.Namespace, parser: argparse.ArgumentParser, *, fund: bool) -> dict[str, Any] | None:
    if not args.expectations_file:
        return None
    if fund:
        parser.error("--expectations-file currently supports company research only")
    try:
        value = json.loads(Path(args.expectations_file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"cannot read --expectations-file: {exc}")
    if not isinstance(value, dict):
        parser.error("--expectations-file must contain a JSON object")
    return value


def run_research_command(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    trade_date: str,
    services: ResearchCommandServices,
) -> int:
    if not args.symbol:
        parser.error(f"--symbol is required when --market {args.market}")
    research_is_fund = args.market == "research" and (
        args.asset_type == "fund"
        or (args.asset_type == "auto" and str(args.symbol).startswith(("5", "15", "16")))
    )
    expectations = _load_expectations(args, parser, fund=research_is_fund)
    reached_primary = None
    if args.primary_evidence_file:
        if research_is_fund:
            parser.error("--primary-evidence-file supports company research only")
        try:
            reached_primary = services.load_reached_primary_evidence(
                args.primary_evidence_file,
                symbol=args.symbol,
                trade_date=trade_date,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read --primary-evidence-file: {exc}")
    try:
        if research_is_fund:
            pack = services.build_fund_evidence(args.symbol, trade_date)
        elif expectations is not None or reached_primary is not None:
            company_options: dict[str, Any] = {}
            if expectations is not None:
                company_options["expectations"] = expectations
            if reached_primary is not None:
                company_options["reached_primary"] = reached_primary
            pack = services.build_company_evidence(
                args.symbol,
                trade_date,
                **company_options,
            )
        else:
            pack = services.build_company_evidence(args.symbol, trade_date)
    except ValueError as exc:
        parser.error(f"invalid research assumptions: {exc}")

    if args.market == "stock-review":
        print(services.render_stock_review(pack))
    elif args.market == "earnings":
        print(services.render_earnings_review(pack))
    elif args.market == "price-move":
        print(services.render_price_move(pack))
    elif args.market == "thesis-create":
        thesis, path = services.create_thesis(pack)
        print(services.render_thesis_create(thesis, path))
    elif args.market == "research":
        requested_lenses = tuple(item.strip() for item in (args.lenses or "").split(",") if item.strip())
        if args.lens and not requested_lenses:
            requested_lenses = (args.lens,)
        try:
            if research_is_fund:
                manifest, workspace = services.build_fund_workspace(
                    pack,
                    root=args.workspace_dir,
                    research_question=args.research_question,
                    lenses=requested_lenses or None,
                )
            else:
                manifest, workspace = services.build_company_workspace(
                    pack,
                    root=args.workspace_dir,
                    lenses=requested_lenses or None,
                    research_question=args.research_question,
                )
        except (KeyError, ValueError) as exc:
            parser.error(str(exc))
        report_path = workspace / manifest["artifacts"]["institutional_report"]["path"]
        print(report_path.read_text(encoding="utf-8"))
        print(f"Research Workspace: {workspace}")
    else:
        thesis, path, changes = services.review_thesis(pack)
        print(services.render_thesis_review(thesis, path, changes))

    if args.emit_evidence:
        (Path.cwd() / f"company_evidence_{pack['symbol']}_{trade_date}.json").write_text(
            json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0
