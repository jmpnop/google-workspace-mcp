# gdocs-tufte — Tufte/CRT Google Docs plugin

An out-of-tree plugin for **google-workspace-mcp**. It publishes Tufte-styled
Google Docs (Classic + CRT) and renders standalone CRT graphics, attaching to the
MCP server through the `workspace_mcp.tools` entry-point seam — core carries no
Tufte code.

## Install

```
/plugin install gdocs-tufte@registry          # skill + MCP tools together
```

or, into the server's venv (registers via the seam on restart):

```
uv pip install -e plugin/
```

## MCP tools

- **`publish_markdown_tufte`** — markdown → styled Google Doc. `style`:
  `classic` (default), `crt`/`crt-c` (cyan), `crt-a` (amber), `crt-g` (green).
  9-phase pipeline: page setup, headings, JetBrains Mono (verified), code blocks
  **+ syntax highlighting**, tables, ASCII-art → image diagrams, pageless.
  Caches title→doc_id and images (SHA-256) in `~/.google_workspace_mcp/cache/tufte/`.
- **`render_tufte_graphic`** — `table` / `bar` / `diagram` / `distribution` → CRT
  PNG (glow/scanlines/vignette), optional Drive upload. For clients that want a
  graphic without a whole doc.

## Layout

```
gdocs_tufte_plugin/
  tools.py            # the two @server.tool() tools
  tufte_publisher.py  # 9-phase pipeline (the one publisher)
  tufte_styles.py     # single palette source (classic, makarina, crt/-a/-g)
  tufte_cache.py      # title->doc_id + image cache
  syntax.py           # rust/sql/json/toml/sh highlighter (pure)
  render/
    ascii_svg.py      # vector diagrams (via core gdocs.docs_svg)
    crt_raster.py     # Pillow CRT effects: tables/bars/diagrams/distribution
    illustration.py   # HTML/CSS -> Chro (CDP/CLI) -> trimmed PNG (Tufte Classic)
    illustration_template.html
  fonts/              # vendored JetBrains Mono (package-relative)
.claude-plugin/plugin.json
.mcp.json             # bundled 'google' server (http://localhost:8000/mcp)
skills/gdocs-tufte/SKILL.md
```

## Renderers

Three behind one intent, style-driven default (`diagrams=auto|svg|crt-raster|illustration`):

| Renderer | Backend | Deps |
|---|---|---|
| `ascii_svg` | pure-Python SVG→PNG | none |
| `crt_raster` | Pillow (true CRT effects) | Pillow |
| `illustration` | HTML/CSS → **Chro** headless (CDP screenshot) | Chro + Pillow + websocket-client |

## Dependencies on core

The plugin imports (never modifies) core: `core.server.server`,
`auth.service_decorator.require_multiple_services`, `core.utils.handle_http_errors`,
and the `gdocs.docs_*` helpers. It runs in-process with the server, so those
resolve without being pip dependencies.

## Develop / test

```
uv venv .venv && uv pip install -e . -e plugin/
# verify the seam registers the tools:
python -c "from importlib.metadata import entry_points as ep; \
import asyncio; from core.server import server; \
[e.load() for e in ep(group='workspace_mcp.tools')]; \
print(asyncio.run(server.get_tool('publish_markdown_tufte')) is not None)"
```
