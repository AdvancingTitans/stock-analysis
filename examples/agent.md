# Agent Workflow Examples

`stock-analysis` works well as a deterministic evidence step before an LLM, notebook, or research agent writes a final market note.

## Daily Recap

Run the CLI, save the Markdown report, and keep the JSON Evidence Pack beside it:

```bash
mkdir -p reports evidence

trade_date="$(date +%Y%m%d)"
stock-analysis --market global --format full --emit-evidence > "reports/daily-recap-${trade_date}.md"

find . -maxdepth 1 -type f \( -name 'evidence_*.json' -o -name 'm[1-6]_*.json' \) -exec mv {} evidence/ \;
```

The Markdown file is the human-readable recap. The JSON files are the audit layer an agent can inspect before summarizing or forwarding the report.

## Agent Prompt

```text
Use stock-analysis as the evidence source for today's market recap.

1. Read the latest reports/daily-recap-*.md file.
2. Read the matching evidence/evidence_*.json file and M1-M6 module files.
3. Summarize only conclusions supported by evidence.
4. If a module is unavailable, state the missing evidence instead of guessing.
5. Keep the final answer research-only and avoid investment advice.
```

## GitHub Actions

Copy [github-actions-daily-recap.yml](github-actions-daily-recap.yml) into `.github/workflows/daily-recap.yml` to run the recap on weekdays and upload the report plus Evidence Pack as workflow artifacts.

The workflow intentionally does not commit generated reports back to the repository. That keeps the default automation reviewable and avoids noisy scheduled commits.
