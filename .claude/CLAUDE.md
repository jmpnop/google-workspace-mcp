# Google Workspace MCP — Project Instructions

These instructions apply automatically to anyone using Claude Code in this repository.

## Tufte Google Docs Publishing

The `publish_markdown_tufte` MCP tool handles all Tufte-style publishing. **Never generate standalone Python publishing scripts.**

When the user says "publish to Google Docs in Tufte style":

1. Read the markdown source (from file or user-provided content)
2. Call the `publish_markdown_tufte` MCP tool with:
   - `markdown_content`: the raw markdown text
   - `title`: document title
   - `style`: `"classic"` (default), `"crt"`, `"crt-a"`, or `"crt-g"`
   - `doc_id` (optional): update an existing document
3. Return the Google Docs link from the response

The tool wraps a Python publishing script (`gdocs/tufte_publisher.py`) that uses the Google Docs API directly — not piecemeal MCP tool calls. The script lives here in the MCP project. NEVER generate publishing scripts in client projects.

The 9-phase pipeline: markdown import, page setup, heading styles, font formatting (JetBrains Mono 400 with verification), code blocks, table styling, ASCII art → SVG → PNG images, and pageless mode.

**Caching:** Title→doc_id is cached (re-publishing updates in place). Images cached by SHA-256 hash. Cache dir: `~/.google_workspace_mcp/cache/tufte/`

### Style reference

- **Classic** — white background, near-black `#1A1A1A` text, landscape 792x612pt, 54pt margins
- **CRT** — near-black `#010101` background, phosphor-colored text (Cyan/Amber/Green), wide 820x1100pt, 0pt side margins
- Font is ALWAYS JetBrains Mono 400 — never serif, never EB Garamond
