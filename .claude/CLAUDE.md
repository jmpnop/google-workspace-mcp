# Google Workspace MCP — Project Instructions

These instructions apply automatically to anyone using Claude Code in this repository.

## Tufte Google Docs Publishing

When the user says "publish to Google Docs in Tufte style":

1. **Read the skill definition FIRST:**
   - Classic (light): `.claude/skills/gdocs-tufte-classic/SKILL.md` (in this repo)
   - CRT (dark): `.claude/skills/gdocs-tufte-crt/SKILL.md` (in this repo)
2. Write a Python publishing script following the pipeline documented in the skill
3. Run via: `uv run --project . python3 <script>` (from this repo root)
4. **MANDATORY:** Convert all ASCII art/box-drawing diagrams to SVG images (render via `rsvg-convert`)
5. Font is ALWAYS JetBrains Mono 400 — never serif, never EB Garamond
6. **MANDATORY:** Verify font applied correctly after formatting (see Font Verification in the skill)
7. Use Python + Google Docs API directly — NEVER use MCP tools for this
8. For CRT variant, read the CRT skill; default to Classic if no variant specified

### Credential Auto-Discovery

Publishing scripts locate OAuth credentials automatically:
- Default: first `*.json` file in `~/.google_workspace_mcp/credentials/`
- Override: set `WORKSPACE_MCP_CREDENTIALS_DIR` environment variable
- Credentials are created by running the MCP server and completing the OAuth flow

### Font: JetBrains Mono

JetBrains Mono is hosted on Google Fonts and works in Google Docs via the API with no local installation. The API silently falls back to Arial if the font name is wrong, so every publishing script must include the `verify_font()` check after applying fonts. If verification fails, stop — do not produce a document in Arial.
