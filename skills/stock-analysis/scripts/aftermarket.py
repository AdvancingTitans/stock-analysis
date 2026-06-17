#!/usr/bin/env python3
"""Backward-compatible wrapper for the v4 evidence-driven engine."""

from __future__ import annotations

import sys

from stock_analysis.app import run


def main(argv: list[str] | None = None) -> int:
    return run(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
