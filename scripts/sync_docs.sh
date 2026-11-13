#!/usr/bin/env bash
# Refresh the docs snapshot the agent answers from.
# Usage: scripts/sync_docs.sh [path-to-adk-chatbot]   (default: ../adk-chatbot)
set -euo pipefail
SRC="${1:-$(dirname "$0")/../../adk-chatbot}"
DEST="$(dirname "$0")/../project_docs_agent/docs"
rm -f "$DEST"/*.md
cp "$SRC"/docs/*.md "$DEST"/
cp "$SRC"/README.md "$DEST"/project-readme.md
echo "Synced $(ls "$DEST" | wc -l | tr -d ' ') files from $SRC at $(git -C "$SRC" rev-parse --short HEAD)"
