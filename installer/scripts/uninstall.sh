#!/bin/bash
# Uninstall workspace-mcp
# Run: sudo bash /usr/local/share/workspace-mcp/uninstall.sh
set -euo pipefail

echo "Removing workspace-mcp..."

rm -f  /usr/local/bin/workspace-mcp
rm -rf /usr/local/lib/workspace-mcp
rm -rf /usr/local/share/workspace-mcp

# Forget the package receipt
pkgutil --forget com.workspace-mcp.pkg 2>/dev/null || true

echo ""
echo "Removed:"
echo "  /usr/local/bin/workspace-mcp"
echo "  /usr/local/lib/workspace-mcp/"
echo "  /usr/local/share/workspace-mcp/"
echo ""
echo "Kept (user data):"
echo "  ~/.google_workspace_mcp/     (credentials & config)"
echo "  ~/.claude/skills/            (Claude Code skills)"
echo ""
echo "To remove user data: rm -rf ~/.google_workspace_mcp"
