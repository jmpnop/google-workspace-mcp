# Google Workspace MCP — Project Instructions

These instructions apply automatically to anyone using Claude Code in this repository.

## Tufte Google Docs Publishing (plugin)

Tufte/CRT publishing lives in the **out-of-tree `gdocs-tufte` plugin** at
[`plugin/`](plugin/) — not in core. It attaches through the `workspace_mcp.tools`
entry-point seam (`main.py`), so core carries no Tufte code. **Never generate
standalone Python publishing scripts** — use the plugin's tools.

The plugin exposes two MCP tools:

- **`publish_markdown_tufte`** — markdown → styled Google Doc.
  1. Read the markdown source (file or content).
  2. Call with `markdown_content` (or `markdown_file`), `title`, `style`
     (`"classic"` default, `"crt"`/`"crt-c"`, `"crt-a"`, `"crt-g"`), optional `doc_id`.
  3. Return the Google Docs link.
- **`render_tufte_graphic`** — render a `table`/`bar`/`diagram`/`distribution`
  to a CRT PNG (glow/scanlines/vignette) with optional Drive upload. For clients
  (e.g. Telegram bots) that want a graphic without a whole doc.

**Code layout** (`plugin/gdocs_tufte_plugin/`): `tufte_publisher.py` (the 9-phase
pipeline), `tufte_styles.py` (single palette source), `tufte_cache.py`,
`syntax.py` (rust/sql/json/toml/sh highlighting), and `render/` — three renderers
behind one interface: `ascii_svg` (vector), `crt_raster` (Pillow CRT effects),
`illustration` (HTML/CSS → Chro/CDP classic). Fonts (JetBrains Mono) are vendored
in `fonts/`.

9-phase pipeline: markdown import, page setup, heading styles, font formatting
(JetBrains Mono 400, verified), code blocks + syntax highlighting, table styling,
ASCII-art → image diagrams, pageless.

**Caching:** Title→doc_id + SHA-256 image cache at `~/.google_workspace_mcp/cache/tufte/`.

**Install:** `/plugin install gdocs-tufte@registry` (delivers the skill + tools), or
`uv pip install -e plugin/` into the server venv (registers via the seam on restart).

### Style reference

- **Classic** — white background, near-black `#1A1A1A` text, landscape 792x612pt, 54pt margins
- **CRT** — near-black `#010101` background, phosphor-colored text (Cyan/Amber/Green), wide 820x1100pt, 0pt side margins
- Font is ALWAYS JetBrains Mono 400 — never serif, never EB Garamond
