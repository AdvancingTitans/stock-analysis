"""Online-only contract check for the annual-report screening source.

Keep this outside pytest: normal CI must remain deterministic and offline.
"""

from __future__ import annotations

import argparse
from datetime import date

from stock_analysis.integrations import fetch_a_share_annual_report_slice


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fiscal-year", type=int, default=date.today().year - 1)
    args = parser.parse_args()
    response = fetch_a_share_annual_report_slice(args.fiscal_year)
    if not response.get("complete"):
        raise SystemExit(f"annual-report contract failed: {response.get('errors') or response}")
    print(
        "annual-report contract ok: "
        f"year={args.fiscal_year} rows={response['reported_total']} pages={response['pages_fetched']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
