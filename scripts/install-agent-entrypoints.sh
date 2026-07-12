#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 "$ROOT/scripts/sync_agent_entrypoints.py"

install_codex() {
  local destination="${CODEX_HOME:-$HOME/.codex}/skills"
  mkdir -p "$destination"
  for source in "$ROOT"/codex-skills/*; do
    cp -R "$source" "$destination/stock-analysis-$(basename "$source")"
  done
  echo "Installed Codex skills in $destination"
}

install_claude() {
  local destination="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/commands"
  mkdir -p "$destination"
  cp "$ROOT"/claude-commands/*.md "$destination/"
  echo "Installed Claude Code commands in $destination"
}

case "${1:-all}" in
  codex) install_codex ;;
  claude) install_claude ;;
  all) install_codex; install_claude ;;
  *) echo "Usage: $0 [codex|claude|all]" >&2; exit 2 ;;
esac
