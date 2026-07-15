---
name: gdocs-tufte
description: Publish Tufte-styled Google Docs — Classic (white, near-black ink) or CRT (near-black, phosphor: cyan/amber/green) — with tables and diagrams, via the workspace MCP publish_markdown_tufte tool. Use when the user says "publish to Google Docs in Tufte style", "Tufte Classic", "CRT style", "dark Tufte", or names a CRT color variant.
allowed-tools: mcp__google__publish_markdown_tufte, Read, Glob
---

# Google Docs — Tufte Publishing (Classic + CRT)

Publish markdown to a fully formatted Google Doc via the `publish_markdown_tufte`
MCP tool. One tool, one font (JetBrains Mono 400), two style families selected by
the `style` argument. The 9-phase pipeline handles page setup, headings, font,
code blocks, table styling, ASCII-art → image diagrams, and pageless mode; it
caches title→doc_id so re-publishing the same title updates in place.

## How to publish

1. **Read the markdown source** (from a file or user-provided content).
2. **Call the tool** with the right `style`:
   ```
   publish_markdown_tufte(
       markdown_content="<markdown>",   # or markdown_file="/abs/path.md"
       title="Document Title",
       style="classic",                  # see variants below
   )
   ```
3. **Return the Google Docs link** from the response.

Prefer `markdown_file` (absolute path) for large documents to avoid inlining.

## Style variants

| `style` | Background | Text | Use for |
|---------|-----------|------|---------|
| `classic` | white | near-black `#1A1A1A` | reports, papers, specs (default) |
| `crt` / `crt-c` | near-black `#010101` | **cyan** phosphor | terminal/dark aesthetic (default CRT) |
| `crt-a` | near-black | **amber** phosphor | amber terminal look |
| `crt-g` | near-black | **green** phosphor | green terminal look |

### Classic
White page, near-black ink, landscape, generous margins. Tables get hairline
styling; diagrams render as crisp vector images. This is the default.

### CRT (C / A / G)
Near-black document background with phosphor-colored text — brightness is the
hierarchy (BRIGHT title/H1 → NORMAL body → DIM/FAINT subheads), never white.
Wide pageless layout, edge-to-edge. Choose the variant by hue: cyan (`crt`),
amber (`crt-a`), green (`crt-g`). Diagrams can render with true CRT effects
(scanlines/glow) via the plugin's raster renderer.

## Tables and diagrams

- **Tables**: standard markdown tables are styled per the active style (hairline
  in Classic; ghost-row/edge-to-edge in CRT).
- **Diagrams**: fenced blocks of ASCII / box-drawing art are converted to images
  in-style (vector for Classic; raster CRT for dark styles).

## Key rules

- **Font is always JetBrains Mono 400** — never serif, never a fallback.
- **CRT inverts Classic** — dark background + phosphor text, brightest level is
  the phosphor color, not white.
- **Re-publish to update**: same `title` updates the existing doc in place.
- **Always use the MCP tool** — never hand-roll a standalone publishing script.
