# Contributing to stock-analysis

Thanks for helping make `stock-analysis` more useful and more reliable.

This project values boring, evidence-first improvements: better public data routes, clearer diagnostics, stronger report templates, and examples that other people can actually run.

## Good First Contributions

- Fix a broken public data-source route.
- Add a small deterministic test around normalization, parsing, or report rendering.
- Improve an example report or screenshot.
- Add a new investor lens only when the evidence requirements are explicit.
- Add an agent workflow example for Codex, Claude Code, Hermes, GitHub Actions, or cron.
- Submit the repo to a high-fit Awesome List using the blurb in `README.md`.

## Before You Open a PR

Run the smallest useful checks:

```bash
uv run --with pytest pytest -q
uv run --with ruff ruff check
```

For data-source changes, also run:

```bash
uv run stock-analysis --market diagnose
```

If a public source is unavailable from your network, keep the failure visible. Do not replace missing fields with zeroes or guessed values.

## Evidence Rules

- Missing data stays missing.
- Prices less than or equal to zero must be filtered or marked invalid.
- Every strong market conclusion should trace back to evidence: quote, turnover, breadth, sector rotation, flow, announcement, or risk event.
- Source, URL, time, and fallback reason belong in evidence metadata, not hidden in prose.
- Reports are research outputs, not investment advice.

## Pull Request Shape

Keep PRs small. A good PR usually does one of these:

- Adds one data-source adapter or fallback.
- Fixes one parsing or normalization bug.
- Improves one report section.
- Adds one focused example.
- Updates docs and screenshots for one workflow.

Use the PR template and include:

- What changed.
- Why it matters.
- Which command verifies it.
- Any known data-source limitations.

## Data-Source Adapter Checklist

- Normalize symbols through the existing normalization helpers.
- Keep source metadata in the evidence object.
- Preserve `None` for unavailable fields.
- Add timeout, retry, or fallback behavior only where the existing codebase already expects it.
- Add a deterministic test for parsing or routing logic.

## Lens Contribution Checklist

Investor lenses are not roleplay prompts. A lens must define:

- Evidence priority.
- Risk vocabulary.
- What counts as insufficient evidence.
- How it changes the report structure.
- Which data gaps must be called out.

Do not add a lens that mainly changes tone.

## Security and Ethics

Do not add broker login, order placement, auto-trading, credential collection, or private account scraping in this repo. Keep the default path public-data-first and research-only.

以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
