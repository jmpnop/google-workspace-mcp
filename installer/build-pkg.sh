#!/bin/bash
# build-pkg.sh — Build macOS .pkg installer for workspace-mcp
# Usage: ./installer/build-pkg.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION=$(python3 -c "
import re
text = open('$PROJECT_DIR/pyproject.toml').read()
print(re.search(r'version\s*=\s*\"(.+?)\"', text).group(1))
")
PKG_NAME="workspace-mcp"
IDENTIFIER="com.workspace-mcp.pkg"

BUILD_DIR="$PROJECT_DIR/build/pkg"
PAYLOAD_DIR="$BUILD_DIR/payload"
COMPONENT_PKG="$BUILD_DIR/workspace-mcp-component.pkg"
OUTPUT_PKG="$PROJECT_DIR/dist/${PKG_NAME}-${VERSION}.pkg"

echo "=== Building $PKG_NAME v$VERSION .pkg installer ==="
echo ""

# ── Clean ────────────────────────────────────────────────────────────────────
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$PROJECT_DIR/dist"

# ── 1. Build payload directory tree ──────────────────────────────────────────
echo "[1/5] Assembling payload..."

# /usr/local/lib/workspace-mcp/src — the Python package
SRC_DEST="$PAYLOAD_DIR/usr/local/lib/workspace-mcp/src"
mkdir -p "$SRC_DEST"

# Copy Python source
cp "$PROJECT_DIR/main.py" "$SRC_DEST/"
cp "$PROJECT_DIR/fastmcp_server.py" "$SRC_DEST/"
cp "$PROJECT_DIR/pyproject.toml" "$SRC_DEST/"
cp "$PROJECT_DIR/README.md" "$SRC_DEST/"
cp "$PROJECT_DIR/LICENSE" "$SRC_DEST/"

# Copy all package directories
for pkg_dir in auth core gmail gdrive gcalendar gdocs gsheets gchat gforms gslides gtasks gcontacts gsearch gappsscript; do
    if [ -d "$PROJECT_DIR/$pkg_dir" ]; then
        cp -R "$PROJECT_DIR/$pkg_dir" "$SRC_DEST/"
    fi
done

# Copy gdocs subdirectories (managers, etc.)
if [ -d "$PROJECT_DIR/gdocs/managers" ]; then
    cp -R "$PROJECT_DIR/gdocs/managers" "$SRC_DEST/gdocs/"
fi

# /usr/local/share/workspace-mcp — shared files
SHARE_DEST="$PAYLOAD_DIR/usr/local/share/workspace-mcp"
mkdir -p "$SHARE_DEST"

# Skills
cp -R "$PROJECT_DIR/.claude/skills" "$SHARE_DEST/skills"

# CLAUDE.md
cp "$PROJECT_DIR/.claude/CLAUDE.md" "$SHARE_DEST/CLAUDE.md"

# Uninstall script
cp "$SCRIPT_DIR/scripts/uninstall.sh" "$SHARE_DEST/uninstall.sh"
chmod 755 "$SHARE_DEST/uninstall.sh"

# .env template
if [ -f "$PROJECT_DIR/.env.oauth21" ]; then
    cp "$PROJECT_DIR/.env.oauth21" "$SHARE_DEST/.env.example"
fi

# Clean build artifacts and macOS resource forks
find "$PAYLOAD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PAYLOAD_DIR" -name "._*" -delete 2>/dev/null || true
find "$PAYLOAD_DIR" -name ".DS_Store" -delete 2>/dev/null || true
find "$PAYLOAD_DIR" -name "*.pyc" -delete 2>/dev/null || true

echo "   Payload: $(find "$PAYLOAD_DIR" -type f | wc -l | tr -d ' ') files"

# ── 2. Prepare scripts ──────────────────────────────────────────────────────
echo "[2/5] Preparing install scripts..."
SCRIPTS_DIR="$BUILD_DIR/scripts"
mkdir -p "$SCRIPTS_DIR"
cp "$SCRIPT_DIR/scripts/preinstall" "$SCRIPTS_DIR/"
cp "$SCRIPT_DIR/scripts/postinstall" "$SCRIPTS_DIR/"
chmod 755 "$SCRIPTS_DIR/preinstall" "$SCRIPTS_DIR/postinstall"

# ── 3. Build component package ───────────────────────────────────────────────
echo "[3/5] Building component package..."
pkgbuild \
    --root "$PAYLOAD_DIR" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --install-location "/" \
    "$COMPONENT_PKG"

# ── 4. Prepare distribution resources ────────────────────────────────────────
echo "[4/5] Preparing distribution resources..."
RESOURCES_DIR="$BUILD_DIR/resources"
mkdir -p "$RESOURCES_DIR"
cp "$SCRIPT_DIR/resources/welcome.html" "$RESOURCES_DIR/"
cp "$SCRIPT_DIR/resources/conclusion.html" "$RESOURCES_DIR/"
cp "$PROJECT_DIR/LICENSE" "$RESOURCES_DIR/"

# ── 5. Build product archive ────────────────────────────────────────────────
echo "[5/5] Building product archive..."
mkdir -p "$(dirname "$OUTPUT_PKG")"
productbuild \
    --distribution "$SCRIPT_DIR/distribution.xml" \
    --resources "$RESOURCES_DIR" \
    --package-path "$BUILD_DIR" \
    "$OUTPUT_PKG"

# ── Done ─────────────────────────────────────────────────────────────────────
PKG_SIZE=$(du -sh "$OUTPUT_PKG" | cut -f1)
echo ""
echo "=== Build complete ==="
echo "   Package: $OUTPUT_PKG"
echo "   Size:    $PKG_SIZE"
echo "   Version: $VERSION"
echo ""
echo "Install with:"
echo "   open $OUTPUT_PKG"
echo ""
echo "Or from the command line:"
echo "   sudo installer -pkg $OUTPUT_PKG -target /"
