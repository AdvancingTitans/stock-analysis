# Roadmap

`stock-analysis` is already useful as a CLI. The next milestone is making it easier for strangers, AI agents, and contributors to trust it quickly.

## Near Term

- Harden the install path: PyPI package, console script, `--help`, and first-run examples must stay in sync.
- Keep README screenshots current with real generated output.
- Add more compact example reports under `reports/`.
- Improve `diagnose` output so source failures are easy to attach to issues.
- Add agent workflow examples for daily recap automation.

## Data Quality

- Expand deterministic tests for quote parsing, symbol normalization, and evidence scoring.
- Add source-specific fixtures for Tencent, Sina, Eastmoney, Tiantian Fund, and Futu public data.
- Improve metadata for fallback events, rate limiting, and browser handoff.
- Keep missing fields visible rather than backfilling them with misleading defaults.

## Market Coverage

- Strengthen A-share board, fund-flow, risk-calendar, and financial snapshot coverage.
- Improve HK/US quote fallback and historical K-line consistency.
- Add more fund profile fields where public routes are stable.
- Document region-specific limitations before expanding new markets.

## Agent Workflows

- Add a GitHub Actions daily recap example.
- Add a cron example for local market notes.
- Add a Codex/Hermes/Claude Code prompt recipe that verifies conclusions against evidence JSON.
- Consider MCP only after the CLI and evidence contract are stable.

## Community

- Keep issue templates focused on data-source failures, feature requests, lens requests, and docs/examples.
- Submit small, well-targeted PRs to finance and AI-agent Awesome Lists.
- Publish share images for GitHub social preview, X/LinkedIn, and Chinese technical communities.

## Out of Scope

- Broker order placement.
- Auto-trading.
- Private account scraping.
- Unverifiable LLM-only recommendations.
- Hiding data-source failures in polished prose.
