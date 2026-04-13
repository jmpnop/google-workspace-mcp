<div align="center">

# Google Workspace MCP Server — Enhanced Edition

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/workspace-mcp.svg)](https://pypi.org/project/workspace-mcp/)

**Google Workspace control through natural language** — extended with document design systems, SVG rendering, git versioning, and programmatic publishing.

Built on [taylorwilsdon/google_workspace_mcp](https://github.com/taylorwilsdon/google_workspace_mcp). Base: 80+ CRUD tools for Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Tasks, Chat, Apps Script, Search. This fork adds the advanced document intelligence and publishing features below.

[What's New](#-whats-new-in-this-fork) • [Tufte Docs](#-tufte-styled-google-docs) • [Quick Start](#-quick-start) • [Tools Reference](#-tools-reference) • [OAuth Setup](#-oauth-setup)

</div>

---

## 🚀 What's New in This Fork

### Tufte Publishing System (Claude Code Skills)

Two complete design systems for publishing Google Docs with Edward Tufte's principles — say *"publish in Tufte style"* in Claude Code and get a formatted document via the Docs API. No manual formatting.

| | **Classic** (light) | **CRT** (dark) |
|---|---|---|
| Background | White | Near-black `#010101` |
| Text | Near-black `#1A1A1A` JetBrains Mono | Phosphor glow (Cyan/Amber/Green) |
| Pipeline | 9-phase: markdown import, page setup, headings, fonts, code blocks, tables, images, pageless | Same core pipeline with CRT color hierarchy |
| Diagrams | ASCII art auto-converted to SVG, rendered as high-res PNG | Same |
| Font verification | Reads doc back to confirm JetBrains Mono applied (API silently falls back to Arial) | Same |

### Advanced Docs Tools

| Tool | What it does |
|---|---|
| `insert_doc_svg` | SVG markup to high-res PNG — renders via rsvg-convert, uploads to Drive, inserts inline with auto aspect ratio and optional caption |
| `set_doc_pageless` | Switch document to pageless (continuous scroll) mode via Docs API |
| `insert_table_of_contents` | Auto-generated TOC from headings (uses bound Apps Script to work around API limitation) |
| `batch_update_doc` | Atomic multi-operation updates with validation — insert, format, replace, add tables/images/page breaks in one call |
| `create_table_with_data` | Create and populate tables atomically — bold headers, cell-by-cell population with index refresh |
| `inspect_doc_structure` | Analyze document topology — elements, tables, safe insertion indices for batch operations |
| `debug_table_structure` | Exact cell positions, dimensions, content — enables reliable table manipulation |
| `update_paragraph_style` | Semantic formatting: heading levels, alignment, spacing, nested lists |
| `get_doc_as_markdown` | Export as clean Markdown with inline or appendix comment integration |

### Document Git Versioning

| Tool | What it does |
|---|---|
| `git_snapshot_doc` | Snapshot a Google Doc as Markdown into a local git repo (`~/.google_workspace_mcp/doc_versions/{doc_id}/`). Only commits when content changes. |
| `git_doc_history` | View commit log for any snapshotted document |
| `git_doc_diff` | Unified diff between any two versions of a document |

### Sheets Formatting

| Tool | What it does |
|---|---|
| `format_sheet_range` | Colors, number formats, text wrapping, alignment, bold/italic, font size |
| `add_conditional_formatting` | Rule-based: NUMBER_GREATER, TEXT_CONTAINS, DATE_BEFORE, CUSTOM_FORMULA, gradient scales |
| `update_conditional_formatting` | Modify existing rules by index |
| `delete_conditional_formatting` | Remove rules by index |

### macOS .pkg Installer

One-click install: creates Python venv, installs dependencies, sets up `workspace-mcp` command, Claude Code skills, credentials directory, and librsvg. Uninstall: `sudo bash /usr/local/share/workspace-mcp/uninstall.sh`

---

## ⚡ Quick Start

### One-Click Install (Claude Desktop)

1. Download `google_workspace_mcp.dxt` from [Releases](https://github.com/taylorwilsdon/google_workspace_mcp/releases)
2. Double-click → Claude Desktop installs automatically
3. Add your Google OAuth credentials in Settings → Extensions

### macOS Installer (.pkg)

1. Download `workspace-mcp-*.pkg` from [Releases](https://github.com/jmpnop/google-workspace-mcp/releases)
2. Double-click to install — sets up `workspace-mcp` command, Python venv, Claude Code skills, and credentials directory
3. Set your Google OAuth credentials and run `workspace-mcp`

To build the .pkg from source: `./installer/build-pkg.sh`

### CLI Install

```bash
# Instant run (no install)
uvx workspace-mcp

# With specific tools only
uvx workspace-mcp --tools gmail drive calendar

# With tool tier
uvx workspace-mcp --tool-tier core
```

### Environment Variables

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
export OAUTHLIB_INSECURE_TRANSPORT=1  # Development only
```

---

## 🎨 Tufte-Styled Google Docs

Three Claude Code skills ship in `.claude/skills/` (auto-installed by the .pkg):

| Skill | Purpose |
|---|---|
| `gdocs-tufte` | One-page quick guide — shows both styles, helps you choose |
| `gdocs-tufte-classic` | Full 9-phase pipeline spec for Classic (light, 450+ lines) |
| `gdocs-tufte-crt` | Full pipeline spec for CRT (dark, 250+ lines) |

### Usage

In Claude Code, say:
- **"publish to Google Docs in Tufte style"** — Classic (white background, near-black ink)
- **"publish in Tufte CRT"** or **"publish in CRT-A"** — CRT (dark, Cyan/Amber/Green variant)

Claude reads the skill, writes a Python publishing script, runs it, and returns the Google Docs link. The script handles markdown import, page setup, heading hierarchy, font application, code block styling, table formatting, SVG diagram rendering, and pageless mode — all via the Docs API.

### CRT Color Variants

| Variant | Invoke with | Look |
|---|---|---|
| Cyan | "CRT" or "CRT-C" | Cyan phosphor on black |
| Amber | "CRT-A" | Amber phosphor on black |
| Green | "CRT-G" | Green phosphor on black |

**Requirements:** OAuth credentials (from setup below) and `brew install librsvg` (for SVG diagram rendering in Classic).

---

## 🛠 Tools Reference

### Gmail (11 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `search_gmail_messages` | Core | Search with Gmail operators, returns message/thread IDs with web links |
| `get_gmail_message_content` | Core | Get full message: subject, sender, body, attachments |
| `get_gmail_messages_content_batch` | Core | Batch retrieve up to 25 messages |
| `send_gmail_message` | Core | Send emails with HTML support, CC/BCC, threading |
| `get_gmail_thread_content` | Extended | Get complete conversation thread |
| `draft_gmail_message` | Extended | Create drafts with threading support |
| `list_gmail_labels` | Extended | List all system and user labels |
| `manage_gmail_label` | Extended | Create, update, delete labels |
| `modify_gmail_message_labels` | Extended | Add/remove labels (archive, trash, etc.) |
| `get_gmail_threads_content_batch` | Complete | Batch retrieve threads |
| `batch_modify_gmail_message_labels` | Complete | Bulk label operations |

**Also includes:** `get_gmail_attachment_content`, `list_gmail_filters`, `create_gmail_filter`, `delete_gmail_filter`

### Google Drive (7 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `search_drive_files` | Core | Search files with Drive query syntax or free text |
| `get_drive_file_content` | Core | Read content from Docs, Sheets, Office files (.docx, .xlsx, .pptx) |
| `create_drive_file` | Core | Create files from content or URL (supports file://, http://, https://) |
| `create_drive_folder` | Core | Create empty folders in Drive or shared drives |
| `list_drive_items` | Extended | List folder contents with shared drive support |
| `update_drive_file` | Extended | Update metadata, move between folders, star, trash |
| `get_drive_file_permissions` | Complete | Check sharing status and permissions |
| `check_drive_file_public_access` | Complete | Verify public link sharing for Docs image insertion |

**Also includes:** `get_drive_file_download_url` for generating download URLs

### Google Calendar (5 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `list_calendars` | Core | List all accessible calendars |
| `get_events` | Core | Query events by time range, search, or specific ID |
| `create_event` | Core | Create events with attendees, reminders, Google Meet, attachments |
| `modify_event` | Core | Update any event property including conferencing |
| `delete_event` | Extended | Remove events |

**Event features:** Timezone support, transparency (busy/free), visibility settings, up to 5 custom reminders

### Google Docs (17 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `get_doc_content` | Core | Extract text from Docs or .docx files (supports tabs) |
| `create_doc` | Core | Create new documents with optional initial content |
| `modify_doc_text` | Core | Insert, replace, format text (bold, italic, colors, fonts, links) |
| `search_docs` | Extended | Find documents by name |
| `find_and_replace_doc` | Extended | Global find/replace with case matching |
| `list_docs_in_folder` | Extended | List Docs in a specific folder |
| `insert_doc_elements` | Extended | Add tables, lists, page breaks |
| `export_doc_to_pdf` | Extended | Export to PDF and save to Drive |
| `insert_doc_svg` | Extended | Insert SVG as PNG (rsvg-convert/cairosvg, auto viewBox sizing) |
| `insert_doc_image` | Complete | Insert images from Drive or URLs |
| `update_doc_headers_footers` | Complete | Modify headers/footers |
| `batch_update_doc` | Complete | Execute multiple operations atomically |
| `insert_table_of_contents` | Complete | Insert auto-generated TOC from document headings |
| `set_doc_pageless` | Complete | Set document to pageless (scrolling) mode via Docs API |
| `inspect_doc_structure` | Complete | Analyze document structure for safe insertion points |
| `create_table_with_data` | Complete | Create and populate tables in one operation |
| `debug_table_structure` | Complete | Debug table cell positions and content |

**Comments:** `read_document_comments`, `create_document_comment`, `reply_to_document_comment`, `resolve_document_comment`

### Google Sheets (13 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `read_sheet_values` | Core | Read cell ranges with formatted output |
| `modify_sheet_values` | Core | Write, update, or clear cell values |
| `create_spreadsheet` | Core | Create new spreadsheets with multiple sheets |
| `list_spreadsheets` | Extended | List accessible spreadsheets |
| `get_spreadsheet_info` | Extended | Get metadata, sheets, conditional formats |
| `format_sheet_range` | Extended | Apply colors, number formats, text wrapping, alignment, bold/italic, font size |
| `create_sheet` | Complete | Add sheets to existing spreadsheets |
| `add_conditional_formatting` | Complete | Add boolean or gradient rules |
| `update_conditional_formatting` | Complete | Modify existing rules |
| `delete_conditional_formatting` | Complete | Remove formatting rules |

**Comments:** `read_spreadsheet_comments`, `create_spreadsheet_comment`, `reply_to_spreadsheet_comment`, `resolve_spreadsheet_comment`

### Google Slides (9 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `create_presentation` | Core | Create new presentations |
| `get_presentation` | Core | Get presentation details with slide text extraction |
| `batch_update_presentation` | Extended | Apply multiple updates (create slides, shapes, etc.) |
| `get_page` | Extended | Get specific slide details and elements |
| `get_page_thumbnail` | Extended | Generate PNG thumbnails |

**Comments:** `read_presentation_comments`, `create_presentation_comment`, `reply_to_presentation_comment`, `resolve_presentation_comment`

### Google Forms (6 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `create_form` | Core | Create forms with title and description |
| `get_form` | Core | Get form details, questions, and URLs |
| `list_form_responses` | Extended | List responses with pagination |
| `set_publish_settings` | Complete | Configure template and authentication settings |
| `get_form_response` | Complete | Get individual response details |
| `batch_update_form` | Complete | Execute batch updates to forms (questions, items, settings) |

### Google Tasks (12 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `list_tasks` | Core | List tasks with filtering, subtask hierarchy preserved |
| `get_task` | Core | Get task details |
| `create_task` | Core | Create tasks with notes, due dates, parent/sibling positioning |
| `update_task` | Core | Update task properties |
| `delete_task` | Extended | Remove tasks |
| `list_task_lists` | Complete | List all task lists |
| `get_task_list` | Complete | Get task list details |
| `create_task_list` | Complete | Create new task lists |
| `update_task_list` | Complete | Rename task lists |
| `delete_task_list` | Complete | Delete task lists (and all tasks) |
| `move_task` | Complete | Reposition or move between lists |
| `clear_completed_tasks` | Complete | Hide completed tasks |

### Google Apps Script (11 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `list_script_projects` | Core | List accessible Apps Script projects |
| `get_script_project` | Core | Get complete project with all files |
| `get_script_content` | Core | Retrieve specific file content |
| `create_script_project` | Core | Create new standalone or bound project |
| `update_script_content` | Core | Update or create script files |
| `run_script_function` | Core | Execute function with parameters |
| `create_deployment` | Extended | Create new script deployment |
| `list_deployments` | Extended | List all project deployments |
| `update_deployment` | Extended | Update deployment configuration |
| `delete_deployment` | Extended | Remove deployment |
| `list_script_processes` | Extended | View recent executions and status |

**Enables:** Cross-app automation, persistent workflows, custom business logic execution, script development and debugging

**Note:** Trigger management is not currently supported via MCP tools.

### Google Contacts (11 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `search_contacts` | Core | Search contacts by name, email, phone |
| `get_contact` | Core | Retrieve detailed contact info |
| `list_contacts` | Core | List contacts with pagination |
| `create_contact` | Core | Create new contacts |
| `update_contact` | Extended | Update existing contacts |
| `delete_contact` | Extended | Delete contacts |
| `list_contact_groups` | Extended | List contact groups/labels |
| `get_contact_group` | Extended | Get group details with members |
| `batch_create_contacts` | Complete | Batch create contacts |
| `batch_update_contacts` | Complete | Batch update contacts |
| `batch_delete_contacts` | Complete | Batch delete contacts |

**Also includes:** `create_contact_group`, `update_contact_group`, `delete_contact_group`, `modify_contact_group_members`

### Google Chat (6 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `get_messages` | Core | Retrieve messages from a space |
| `send_message` | Core | Send messages with optional threading |
| `search_messages` | Core | Search across chat history |
| `create_reaction` | Core | Add emoji reaction to a message |
| `list_spaces` | Extended | List rooms and DMs |
| `download_chat_attachment` | Extended | Download attachment from a chat message |

### Google Custom Search (3 tools)

| Tool | Tier | Description |
|------|------|-------------|
| `search_custom` | Core | Web search with filters (date, file type, language, safe search) |
| `search_custom_siterestrict` | Extended | Search within specific domains |
| `get_search_engine_info` | Complete | Get search engine metadata |

**Requires:** `GOOGLE_PSE_API_KEY` and `GOOGLE_PSE_ENGINE_ID` environment variables

---

## 📊 Tool Tiers

Choose a tier based on your needs:

| Tier | Tools | Use Case |
|------|-------|----------|
| **Core** | ~30 | Essential operations: search, read, create, send |
| **Extended** | ~50 | Core + management: labels, folders, batch ops |
| **Complete** | ~80 | Full API: comments, headers, admin functions |

```bash
uvx workspace-mcp --tool-tier core      # Start minimal
uvx workspace-mcp --tool-tier extended  # Add management
uvx workspace-mcp --tool-tier complete  # Everything
```

Mix tiers with specific services:
```bash
uvx workspace-mcp --tools gmail drive --tool-tier extended
```

---

## ⚙ Configuration

### Required

| Variable | Description |
|----------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client ID from Google Cloud |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret |

### Optional

| Variable | Description |
|----------|-------------|
| `USER_GOOGLE_EMAIL` | Default email for single-user mode |
| `GOOGLE_PSE_API_KEY` | Custom Search API key |
| `GOOGLE_PSE_ENGINE_ID` | Programmable Search Engine ID |
| `MCP_ENABLE_OAUTH21` | Enable OAuth 2.1 multi-user support |
| `WORKSPACE_MCP_STATELESS_MODE` | No file writes (container-friendly) |
| `EXTERNAL_OAUTH21_PROVIDER` | External OAuth flow with bearer tokens |
| `WORKSPACE_MCP_BASE_URI` | Server base URL (default: `http://localhost`) |
| `WORKSPACE_MCP_PORT` | Server port (default: `8000`) |
| `WORKSPACE_EXTERNAL_URL` | External URL for reverse proxy setups |
| `GOOGLE_MCP_CREDENTIALS_DIR` | Custom credentials storage path |

---

## 🔐 OAuth Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Navigate to **APIs & Services → Credentials**
4. Click **Create Credentials → OAuth Client ID**
5. Select **Desktop Application**
6. Download credentials

### 2. Enable APIs

Click to enable each API:

- [Calendar](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com)
- [Drive](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com)
- [Gmail](https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com)
- [Docs](https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com)
- [Sheets](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com)
- [Slides](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com)
- [Forms](https://console.cloud.google.com/flows/enableapi?apiid=forms.googleapis.com)
- [Tasks](https://console.cloud.google.com/flows/enableapi?apiid=tasks.googleapis.com)
- [Chat](https://console.cloud.google.com/flows/enableapi?apiid=chat.googleapis.com)
- [People (Contacts)](https://console.cloud.google.com/flows/enableapi?apiid=people.googleapis.com)
- [Custom Search](https://console.cloud.google.com/flows/enableapi?apiid=customsearch.googleapis.com)

### 3. First Authentication

When you first call a tool:
1. Server returns an authorization URL
2. Open URL in browser, authorize access
3. Paste the authorization code when prompted
4. Credentials are cached for future use

---

## 🚀 Transport Modes

### Stdio (Default)

Best for Claude Desktop and local MCP clients:

```bash
uvx workspace-mcp
```

### HTTP (Streamable)

For web interfaces, debugging, or multi-client setups:

```bash
uvx workspace-mcp --transport streamable-http
```

Access at `http://localhost:8000/mcp/`

### Docker

```bash
docker build -t workspace-mcp .
docker run -p 8000:8000 \
  -e GOOGLE_OAUTH_CLIENT_ID="..." \
  -e GOOGLE_OAUTH_CLIENT_SECRET="..." \
  workspace-mcp --transport streamable-http
```

---

## 🔧 Client Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "uvx",
      "args": ["workspace-mcp", "--tool-tier", "core"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "your-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "your-secret",
        "OAUTHLIB_INSECURE_TRANSPORT": "1"
      }
    }
  }
}
```

### LM Studio

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "uvx",
      "args": ["workspace-mcp"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "your-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "your-secret",
        "OAUTHLIB_INSECURE_TRANSPORT": "1",
        "USER_GOOGLE_EMAIL": "you@example.com"
      }
    }
  }
}
```

### VS Code

```json
{
  "servers": {
    "google-workspace": {
      "url": "http://localhost:8000/mcp/",
      "type": "http"
    }
  }
}
```

### Claude Code

```bash
claude mcp add --transport http workspace-mcp http://localhost:8000/mcp
```

---

## 🏗 Architecture

```
google_workspace_mcp/
├── auth/                 # OAuth 2.0/2.1, credential storage, decorators
├── core/                 # MCP server, tool registry, utilities
├── gcalendar/           # Calendar tools
├── gchat/               # Chat tools
├── gdocs/               # Docs tools + managers (tables, headers, batch)
├── gdrive/              # Drive tools + helpers
├── gforms/              # Forms tools
├── gmail/               # Gmail tools
├── gsearch/             # Custom Search tools
├── gsheets/             # Sheets tools + helpers
├── gslides/             # Slides tools
├── gtasks/              # Tasks tools
└── main.py              # Entry point
```

### Key Patterns

**Service Decorator:** All tools use `@require_google_service()` for automatic authentication with 30-minute service caching.

```python
@server.tool()
@require_google_service("gmail", "gmail_read")
async def search_gmail_messages(service, user_google_email: str, query: str):
    # service is injected automatically
    ...
```

**Multi-Service Tools:** Some tools need multiple APIs:

```python
@require_multiple_services([
    {"service_type": "drive", "scopes": "drive_read", "param_name": "drive_service"},
    {"service_type": "docs", "scopes": "docs_read", "param_name": "docs_service"},
])
async def get_doc_content(drive_service, docs_service, ...):
    ...
```

---

## 🧪 Development

```bash
git clone https://github.com/taylorwilsdon/google_workspace_mcp.git
cd google_workspace_mcp

# Install with dev dependencies
uv sync --group dev

# Run locally
uv run main.py

# Run tests
uv run pytest

# Lint
uv run ruff check .
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**[Documentation](https://workspacemcp.com)** • **[Issues](https://github.com/taylorwilsdon/google_workspace_mcp/issues)** • **[PyPI](https://pypi.org/project/workspace-mcp/)**

</div>
