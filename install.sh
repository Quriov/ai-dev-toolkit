#!/bin/bash
set -e
CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR/rules/common" "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/commands" "$CLAUDE_DIR/skills"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing AI Dev Toolkit..."
cp "$SCRIPT_DIR/rules/"*.md "$CLAUDE_DIR/rules/common/" && echo "Rules installed"
cp "$SCRIPT_DIR/hooks/"*.js "$CLAUDE_DIR/hooks/" && echo "Hooks installed"
cp "$SCRIPT_DIR/commands/"*.md "$CLAUDE_DIR/commands/" && echo "Commands installed"
if [ -d "$SCRIPT_DIR/skills" ]; then
    for skill_dir in "$SCRIPT_DIR/skills"/*/; do
        if [ -d "$skill_dir" ]; then
            skill_name=$(basename "$skill_dir")
            cp -r "$skill_dir" "$CLAUDE_DIR/skills/" && echo "Skill installed: $skill_name"
        fi
    done
fi
echo ""
echo "Done! Add this to ~/.claude/settings.json hooks.Stop:"
echo '  {"type": "command", "command": "node \"~/.claude/hooks/dev-loop-check.js\""}'
