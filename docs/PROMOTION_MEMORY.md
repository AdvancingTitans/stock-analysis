# stock-analysis Promotion Memory

Last updated: 2026-07-09

## Project Positioning

- Repository: https://github.com/AdvancingTitans/stock-analysis
- Short pitch: evidence-driven market recap CLI for A/HK/US stocks, funds, and portfolios.
- Agent angle: emits Markdown reports plus JSON Evidence Packs so AI agents can summarize, audit, and reuse market evidence without inventing unsupported claims.
- Keep descriptions factual. Avoid implying live trading, order execution, or investment advice.

## Prepared Assets

- README has been rewritten as a product landing page.
- Social preview asset exists at `assets/social-preview.png`; GitHub repository social preview still needs manual setting in repo settings if not already done.
- Agent examples:
  - `examples/agent.md`
  - `examples/github-actions-daily-recap.yml`
- Contribution/promotional docs:
  - `CONTRIBUTING.md`
  - `docs/PROMOTION.md`

## Submitted PRs

First wave:

- https://github.com/leoncuhk/awesome-quant-ai/pull/39
- https://github.com/georgezouq/awesome-ai-in-finance/pull/183
- https://github.com/ashishpatel26/500-AI-Agents-Projects/pull/145

Second wave:

- https://github.com/thuquant/awesome-quant/pull/48
- https://github.com/wangzhe3224/awesome-systematic-trading/pull/124
- https://github.com/jim-schwoebel/awesome_ai_agents/pull/385
- https://github.com/caramaschiHG/awesome-ai-agents-2026/pull/424

## External PR Workspaces

External awesome-list clones are under `/tmp/stock-analysis-awesome-prs/`.

- `awesome-quant`
- `awesome-ai-in-finance`
- `500-AI-Agents-Projects`
- `awesome-quant-ai`
- `wangzhe-awesome-systematic-trading`
- `awesome_ai_agents`
- `awesome-ai-agents-2026`

Each PR uses branch `add-stock-analysis` on the `AdvancingTitans` fork unless noted otherwise.

## Follow-Up Rules

- Weekly automation: `stock-analysis-awesome-pr-weekly-follow-up` runs every Saturday at 04:00 local time to inspect submitted PRs and apply low-risk review fixes directly.
- Use `gh pr view <number> --repo <owner/repo> --json state,isDraft,comments,reviews,reviewDecision,statusCheckRollup,headRefOid,url`.
- Also check review comments with `gh api repos/<owner>/<repo>/pulls/<number>/comments --paginate`.
- If feedback is style, capitalization, placement, or description length and the fix is low-risk, edit the fork directly, commit, and push.
- Do not respond to review comments unless the user asks or a human maintainer needs an explanation.
- If a PR is merged or closed as accepted, record it here.
- If a maintainer rejects because the target category does not fit, do not argue; update the memory with the reason and skip similar targets.
- Skip MCP-only lists until this project exposes a real MCP server.

## Next Candidate Targets

- `paperswithbacktest/awesome-systematic-trading`: high stars, but last push looked older than the active fork; consider only after current systematic-trading PR outcome.
- `alvinreal/awesome-opensource-ai`: broad open-source AI list; possible if positioning as an agent-ready data/research tool.
- `Prat011/awesome-llm-skills`: possible only if promoting the in-repo skill/workflow angle, not the CLI alone.

## Local Verification Notes

- Main repo docs/tests previously passed after adding agent examples:
  - `~/.local/bin/uv run --with pytest pytest tests/test_package_metadata.py tests/test_skill_docs.py tests/test_independence.py::test_user_facing_docs_do_not_route_to_young_stock_cli -q`
  - `~/.local/bin/uv run --with ruff ruff check`
- `tests/test_independence.py` is sensitive to user-facing docs. Avoid adding forbidden CLI options such as `--lens` to README or skill docs.
