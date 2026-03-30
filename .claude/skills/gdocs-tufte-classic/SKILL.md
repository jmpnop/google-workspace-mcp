---
name: gdocs-tufte-classic
description: Creates and formats Google Docs using the Tufte Classic design — JetBrains Mono 400, near-black (#1A1A1A) text on white background, pageless landscape, 54pt margins, heading hierarchy via size only (24/18/14/12pt). Use when creating or formatting Google Docs in the clean Tufte style.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Google Docs — Tufte Classic Design System

Create publication-quality Google Docs using the Docs API with Edward Tufte design principles adapted for screen reading: monochrome near-black typography, single monospace font, minimal spacing, pageless landscape layout.

## When to use this skill

When the user asks to create, format, or style a Google Doc in "Tufte" or "Tufte Classic" style. This is the light/white background variant. For dark background with colored text, see `gdocs-tufte-crt`.

**Reference document:** StarPredict — `12iQQjyC8JazWUI7A0Iwt9B7UGIpyccqw7bHNqBgdtpw`

## Prerequisites

- Python with Google API libraries (run via `uv run --project /Users/pasha/PycharmProjects/google_workspace_mcp python3`)
- OAuth credentials at `~/.google_workspace_mcp/credentials/polikashin@celestialtech.io.json`

## Credential Boilerplate

```python
import json, os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

cred_path = os.path.expanduser("~/.google_workspace_mcp/credentials/polikashin@celestialtech.io.json")
with open(cred_path) as f:
    data = json.load(f)
creds = Credentials(
    token=data.get("token"),
    refresh_token=data.get("refresh_token"),
    token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
    client_id=data.get("client_id"),
    client_secret=data.get("client_secret"),
    scopes=data.get("scopes")
)
if creds.expired:
    creds.refresh(Request())
docs_svc = build('docs', 'v1', credentials=creds)
drive_svc = build('drive', 'v3', credentials=creds)
```

## Design Principles

1. **Single font family** — JetBrains Mono weight 400 throughout. No weight variation except bold on H2.
2. **Monochrome** — near-black `#1A1A1A` (rgb 0.102) for all text. No colored headings, no accent colors.
3. **Heading hierarchy via size** — Title 24pt, H1 18pt, H2 14pt bold, H3/H4 12pt (gray variants).
4. **White background** — no tint, no cream, pure white (default, do NOT set background color).
5. **Pageless landscape** — continuous scroll, no page breaks, landscape orientation.
6. **Minimal spacing** — 3pt spaceBelow on all elements, 24pt spaceAbove on H2 only.
7. **No decoration** — no borders, no rules, no chartjunk. Content speaks for itself.

## Color Palette

```python
# The only color used (besides default white background)
INK = {"red": 0.102, "green": 0.102, "blue": 0.102}  # #1A1A1A — all text

# Heading grays (H3, H4 only)
H3_GRAY = {"red": 0.263, "green": 0.263, "blue": 0.263}  # Slightly lighter
H4_GRAY = {"red": 0.4, "green": 0.4, "blue": 0.4}        # Noticeably lighter
```

## Typography

| Element | Size | Weight | Color | Extra |
|---------|------|--------|-------|-------|
| TITLE | 24pt | 400 | INK | spaceBelow 3pt |
| HEADING_1 | 18pt | 400 | INK | spaceBelow 3pt |
| HEADING_2 | 14pt | 400 | INK | **bold=True**, spaceAbove 24pt, spaceBelow 3pt |
| HEADING_3 | 12pt | 400 | H3_GRAY | |
| HEADING_4 | 12pt | 400 | H4_GRAY | italic=True |
| NORMAL_TEXT | 12pt | 400 | INK | lineSpacing 115, spaceBelow 3pt |

## Document Setup

```python
PAGE_WIDTH_PT = 792
PAGE_HEIGHT_PT = 612  # Landscape
MARGIN_PT = 54        # All four sides
LINE_SPACING = 115    # Percentage
SPACE_BELOW_PT = 3    # Universal
H2_SPACE_ABOVE_PT = 24
```

## Formatting Approach

The Google Docs API does not support `updateNamedStyle` as a batchUpdate request type. Instead, apply formatting directly to each paragraph and text range. The order of operations:

### Step 1: Create document (if new)

```python
doc = docs_svc.documents().create(body={"title": "Document Title"}).execute()
doc_id = doc["documentId"]
```

### Step 2: Insert content

Parse the markdown source and insert as plain text first:

```python
# Insert all text content via insertText requests
# Track paragraph boundaries (startIndex, endIndex) for later formatting
requests = []
for section in sections:
    requests.append({
        "insertText": {
            "location": {"index": cursor},
            "text": section["text"] + "\n"
        }
    })
```

### Step 3: Set document style (pageless, margins)

```python
requests.append({
    "updateDocumentStyle": {
        "documentStyle": {
            "pageSize": {
                "width": {"magnitude": 792, "unit": "PT"},
                "height": {"magnitude": 612, "unit": "PT"},
            },
            "marginTop": {"magnitude": 54, "unit": "PT"},
            "marginBottom": {"magnitude": 54, "unit": "PT"},
            "marginLeft": {"magnitude": 54, "unit": "PT"},
            "marginRight": {"magnitude": 54, "unit": "PT"},
            "useCustomHeaderFooterMargins": False,
            "flipPageOrientation": False,
        },
        "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight,useCustomHeaderFooterMargins,flipPageOrientation",
    }
})
```

### Step 4: Reset all text to base style

Apply a blanket text style across the entire body to clear any prior formatting:

```python
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": 1, "endIndex": end_index},
        "textStyle": {
            "weightedFontFamily": {"fontFamily": "JetBrains Mono", "weight": 400},
            "fontSize": {"magnitude": 12, "unit": "PT"},
            "foregroundColor": {"color": {"rgbColor": INK}},
            "bold": False,
            "italic": False,
            "underline": False,
            "strikethrough": False,
        },
        "fields": "weightedFontFamily,fontSize,foregroundColor,bold,italic,underline,strikethrough",
    }
})
```

### Step 5: Set paragraph styles

For each paragraph, set the appropriate `namedStyleType` and spacing:

```python
# Title paragraph
requests.append({
    "updateParagraphStyle": {
        "range": {"startIndex": title_start, "endIndex": title_end},
        "paragraphStyle": {
            "namedStyleType": "TITLE",
            "spaceBelow": {"magnitude": 3, "unit": "PT"},
        },
        "fields": "namedStyleType,spaceBelow",
    }
})

# H1 paragraphs
requests.append({
    "updateParagraphStyle": {
        "range": {"startIndex": h1_start, "endIndex": h1_end},
        "paragraphStyle": {
            "namedStyleType": "HEADING_1",
            "spaceBelow": {"magnitude": 3, "unit": "PT"},
        },
        "fields": "namedStyleType,spaceBelow",
    }
})

# H2 paragraphs (note spaceAbove)
requests.append({
    "updateParagraphStyle": {
        "range": {"startIndex": h2_start, "endIndex": h2_end},
        "paragraphStyle": {
            "namedStyleType": "HEADING_2",
            "spaceAbove": {"magnitude": 24, "unit": "PT"},
            "spaceBelow": {"magnitude": 3, "unit": "PT"},
        },
        "fields": "namedStyleType,spaceAbove,spaceBelow",
    }
})

# Body paragraphs
requests.append({
    "updateParagraphStyle": {
        "range": {"startIndex": p_start, "endIndex": p_end},
        "paragraphStyle": {
            "namedStyleType": "NORMAL_TEXT",
            "lineSpacing": 115,
            "spaceBelow": {"magnitude": 3, "unit": "PT"},
            "spacingMode": "NEVER_COLLAPSE",
        },
        "fields": "namedStyleType,lineSpacing,spaceBelow,spacingMode",
    }
})
```

### Step 6: Apply text style overrides for headings

After paragraph styles are set, apply size/bold/color overrides to heading text ranges:

```python
# Title text: 24pt
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": title_start, "endIndex": title_end},
        "textStyle": {
            "weightedFontFamily": {"fontFamily": "JetBrains Mono", "weight": 400},
            "fontSize": {"magnitude": 24, "unit": "PT"},
            "foregroundColor": {"color": {"rgbColor": INK}},
        },
        "fields": "weightedFontFamily,fontSize,foregroundColor",
    }
})

# H1 text: 18pt
# ...same pattern, magnitude 18...

# H2 text: 14pt bold
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": h2_start, "endIndex": h2_end},
        "textStyle": {
            "weightedFontFamily": {"fontFamily": "JetBrains Mono", "weight": 400},
            "fontSize": {"magnitude": 14, "unit": "PT"},
            "foregroundColor": {"color": {"rgbColor": INK}},
            "bold": True,
        },
        "fields": "weightedFontFamily,fontSize,foregroundColor,bold",
    }
})
```

### Step 7: Set pageless mode via Drive API

```python
drive_svc.files().update(
    fileId=doc_id,
    body={"contentRestrictions": []},  # placeholder — pageless set via Docs API
).execute()
```

Note: Pageless mode is enabled by the document style update with the landscape page dimensions. The Google Docs web UI will show it as pageless.

## Tables

Markdown tables should be converted to Google Docs tables:

- Header row: same font, same size, bold text
- Body rows: normal weight
- No cell fills, no borders beyond default thin rules
- Keep the monochrome aesthetic — do not add colored cells

## Key Rules

- **Never use colored text** — all text is INK (#1A1A1A) except H3 (0.263 gray) and H4 (0.4 gray)
- **Never set background color** — white is the default
- **Bold only on H2** — no other bold usage in the document structure
- **No font weight variation** — always weight 400, use bold property only for H2
- **Strip markdown formatting marks** — remove `#`, `**`, `|` table pipes, etc. before inserting text
- **spaceBelow 3pt everywhere** — universal spacing rule
