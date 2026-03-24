#!/bin/bash
set -e
CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR/rules/common" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/commands"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing AI Dev Toolkit..."
cp "$SCRIPT_DIR/rules/"*.md "$CLAUDE_DIR/rules/common/" && echo "Rules installed"
cp "$SCRIPT_DIR/hooks/"*.js "$CLAUDE_DIR/hooks/" && echo "Hooks installed"
cp "$SCRIPT_DIR/commands/"*.md "$CLAUDE_DIR/commands/" && echo "Commands installed"
echo ""
echo "Done! Add this to ~/.claude/settings.json hooks.Stop:"
echo '  {"type": "command", "command": "node \"~/.claude/hooks/dev-loop-check.js\""}'
