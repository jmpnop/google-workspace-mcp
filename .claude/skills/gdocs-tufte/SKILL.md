---
name: gdocs-tufte
description: Quick reference for Tufte-styled Google Docs — shows both styles side by side, helps the user choose, and explains how to publish. Show this guide when the user asks about Tufte styles.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Tufte Google Docs — Quick Guide

Two design systems for publishing beautiful Google Docs via the Docs API.

## The Two Styles

```
CLASSIC (light)                          CRT (dark)
+------------------------------------+   +------------------------------------+
|                                    |   |                                    |
|  Title Text               24pt    |   |  Title Text               28pt    |
|  Near-black on white              |   |  Phosphor glow on black           |
|                                    |   |                                    |
|  Body text in 12pt                |   |  Body text in 11pt                |
|  JetBrains Mono 400               |   |  JetBrains Mono 400               |
|  #1A1A1A ink on white bg          |   |  Colored text on #010101 bg       |
|                                    |   |                                    |
|  Landscape, pageless, 54pt margins |   |  Wide pageless, 0pt side margins  |
+------------------------------------+   +------------------------------------+
```

| | Classic | CRT |
|---|---|---|
| **Background** | White (default) | Near-black `#010101` |
| **Text color** | `#1A1A1A` (all text) | Phosphor color (C/A/G) |
| **Title** | 24pt, weight 400 | 28pt, bold, bright |
| **H1** | 18pt, weight 400 | 22pt, bold, bright |
| **H2** | 14pt, bold | 16pt, bold, normal |
| **Body** | 12pt | 11pt |
| **Margins** | 54pt all sides | 18pt top/bottom, 0 sides |
| **Diagrams** | ASCII -> SVG -> PNG (mandatory) | Same pipeline or omit |
| **Best for** | Reports, specs, documentation | Dashboards, terminal-style docs |

### CRT Color Variants

| Variant | Invoke with | Bright | Normal |
|---|---|---|---|
| Cyan | "CRT" or "CRT-C" | `(0, 1, 1)` | `(0, 0.8, 0.8)` |
| Amber | "CRT-A" | `(1, 0.6, 0)` | `(0.8, 0.48, 0)` |
| Green | "CRT-G" | `(0, 1, 0)` | `(0, 0.8, 0)` |

## How to Publish

Say one of:
- **"publish to Google Docs in Tufte style"** -> Classic (light)
- **"publish in Tufte CRT"** or **"publish in CRT-A"** -> CRT (dark, with variant)

Claude will:
1. Read the full skill definition (Classic or CRT)
2. Write a Python publishing script following the 9-phase pipeline
3. Run it via `uv run --project . python3 <script>`
4. Convert any ASCII diagrams to SVG images (Classic)
5. Verify JetBrains Mono applied correctly
6. Return the Google Docs link

## Prerequisites

- **OAuth credentials:** Run the MCP server once and complete the Google OAuth flow. Credentials are stored in `~/.google_workspace_mcp/credentials/`
- **Font:** JetBrains Mono is on Google Fonts — no local install needed. The script verifies it applied.
- **SVG rendering (Classic only):** `brew install librsvg` for `rsvg-convert`

## Shared Design Rules

Both styles follow Edward Tufte's principles:
- Single font family (JetBrains Mono) throughout
- No decoration, no borders, no chartjunk
- Heading hierarchy via size, not color
- Content density over whitespace
- Data-ink ratio maximization
