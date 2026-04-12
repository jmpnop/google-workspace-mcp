---
name: gdocs-tufte-crt
description: Creates and formats Google Docs using the Tufte CRT design — JetBrains Mono on near-black background with phosphor-colored text. Three color variants: C (Cyan, default), A (Amber), G (Green). Use when creating dark-themed Google Docs with CRT/terminal aesthetic.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Google Docs — Tufte CRT Design System

Create dark-themed Google Docs using the Docs API with CRT/terminal aesthetic: near-black background, phosphor-colored monospace text, scanline-inspired spacing. A dark variation of the Tufte Classic design system.

## When to use this skill

When the user asks to create or format a Google Doc in "Tufte CRT", "CRT style", or "dark Tufte" style. Also when they specify a color variant: "CRT-C" (cyan), "CRT-A" (amber), "CRT-G" (green).

**Reference:** A dark variation of the Tufte Classic design system. See `gdocs-tufte-classic` for the light variant.

## Color Variants

| Variant | Flag | Default | Heading Color | Body Color | Dim | Faint | Ghost |
|---------|------|---------|--------------|------------|-----|-------|-------|
| **Cyan** | C | Yes | `(0, 1, 1)` | `(0, 0.8, 0.8)` | `(0, 0.55, 0.55)` | `(0, 0.314, 0.314)` | `(0.004, 0.07, 0.07)` |
| **Amber** | A | No | `(1, 0.6, 0)` | `(0.8, 0.48, 0)` | `(0.55, 0.33, 0)` | `(0.314, 0.188, 0)` | `(0.07, 0.042, 0.004)` |
| **Green** | G | No | `(0, 1, 0)` | `(0, 0.8, 0)` | `(0, 0.55, 0)` | `(0, 0.314, 0)` | `(0.004, 0.07, 0.004)` |

## Prerequisites

- Python with Google API libraries (run via `uv run --project <WORKSPACE_MCP_PROJECT_DIR> python3`, where `<WORKSPACE_MCP_PROJECT_DIR>` is the path to the cloned `google_workspace_mcp` repo)
- OAuth credentials in `~/.google_workspace_mcp/credentials/` (auto-detected — any `*.json` file; set `WORKSPACE_MCP_CREDENTIALS_DIR` to override)

## Font — JetBrains Mono

JetBrains Mono is available on [Google Fonts](https://fonts.google.com/specimen/JetBrains+Mono) and works natively in Google Docs via the API — no local installation required. The API silently falls back to Arial if the font is unavailable, so **always verify** after applying fonts (see Step 3 Verification below).

## Credential Boilerplate

```python
import glob, json, os
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

cred_dir = Path(os.environ.get("WORKSPACE_MCP_CREDENTIALS_DIR",
           Path.home() / ".google_workspace_mcp/credentials"))
cred_files = sorted(cred_dir.glob("*.json"))
if not cred_files:
    raise FileNotFoundError(f"No credential files found in {cred_dir}")
cred_path = cred_files[0]
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

1. **CRT phosphor aesthetic** — bright heading text fades through body, dim, faint, ghost levels.
2. **Near-black background** — `#010101` (rgb 0.004) simulates CRT off-state.
3. **Single font family** — JetBrains Mono throughout, weight hierarchy for emphasis.
4. **Color temperature hierarchy** — brightest = most important, ghost = structural hints.
5. **Pageless wide** — continuous scroll, minimal margins for maximum terminal feel.
6. **Compact spacing** — tighter than Tufte Classic, mimicking terminal line height.

## Color Palette (Cyan variant — default)

```python
# Background
NEAR_BLACK = {"red": 0.004, "green": 0.004, "blue": 0.004}

# ── Cyan (C) ──
BRIGHT   = {"red": 0.0, "green": 1.0,   "blue": 1.0}    # Title, H1 — full phosphor
NORMAL   = {"red": 0.0, "green": 0.8,   "blue": 0.8}    # Body text, H2
DIM      = {"red": 0.0, "green": 0.55,  "blue": 0.55}   # H3, secondary
FAINT    = {"red": 0.0, "green": 0.314, "blue": 0.314}  # H4, footers, sources
GHOST    = {"red": 0.004, "green": 0.07, "blue": 0.07}  # Table backgrounds, code bg
```

### Amber variant (A)

```python
BRIGHT   = {"red": 1.0,   "green": 0.6,   "blue": 0.0}
NORMAL   = {"red": 0.8,   "green": 0.48,  "blue": 0.0}
DIM      = {"red": 0.55,  "green": 0.33,  "blue": 0.0}
FAINT    = {"red": 0.314, "green": 0.188, "blue": 0.0}
GHOST    = {"red": 0.07,  "green": 0.042, "blue": 0.004}
```

### Green variant (G)

```python
BRIGHT   = {"red": 0.0, "green": 1.0,   "blue": 0.0}
NORMAL   = {"red": 0.0, "green": 0.8,   "blue": 0.0}
DIM      = {"red": 0.0, "green": 0.55,  "blue": 0.0}
FAINT    = {"red": 0.0, "green": 0.314, "blue": 0.0}
GHOST    = {"red": 0.004, "green": 0.07, "blue": 0.004}
```

## Typography

| Element | Size | Color Level | Extra |
|---------|------|-------------|-------|
| TITLE | 28pt | BRIGHT | Bold, spaceBelow 3pt |
| HEADING_1 | 22pt | BRIGHT | Bold, spaceBelow 3pt |
| HEADING_2 | 16pt | NORMAL | Bold, spaceAbove 18pt, spaceBelow 3pt |
| HEADING_3 | 13pt | DIM | spaceAbove 12pt |
| HEADING_4 | 12pt | FAINT | Italic |
| NORMAL_TEXT | 11pt | NORMAL | lineSpacing 115, spaceBelow 3pt |
| Table text | 10pt | NORMAL | |
| Code blocks | 9pt | NORMAL | Background: GHOST |

## Document Setup

```python
PAGE_WIDTH_PT = 820     # Wide pageless
PAGE_HEIGHT_PT = 1100   # Tall for pageless scroll
MARGIN_TOP_PT = 18
MARGIN_BOTTOM_PT = 18
MARGIN_LEFT_PT = 0      # Edge-to-edge for terminal feel
MARGIN_RIGHT_PT = 0
LINE_SPACING = 115
```

## Formatting Approach

### Step 1: Create document and insert content

Same as Tufte Classic — create doc, insert plain text, track paragraph boundaries.

### Step 2: Set document style

```python
requests = [{
    "updateDocumentStyle": {
        "documentStyle": {
            "pageSize": {
                "width": {"magnitude": 820, "unit": "PT"},
                "height": {"magnitude": 1100, "unit": "PT"},
            },
            "marginTop": {"magnitude": 18, "unit": "PT"},
            "marginBottom": {"magnitude": 18, "unit": "PT"},
            "marginLeft": {"magnitude": 0, "unit": "PT"},
            "marginRight": {"magnitude": 0, "unit": "PT"},
            "background": {
                "color": {"color": {"rgbColor": NEAR_BLACK}}
            },
        },
        "fields": "pageSize,marginTop,marginBottom,marginLeft,marginRight,background",
    }
}]
```

### Step 3: Reset all text to base CRT style

```python
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": 1, "endIndex": end_index},
        "textStyle": {
            "weightedFontFamily": {"fontFamily": "JetBrains Mono", "weight": 400},
            "fontSize": {"magnitude": 11, "unit": "PT"},
            "foregroundColor": {"color": {"rgbColor": NORMAL}},
            "bold": False,
            "italic": False,
        },
        "fields": "weightedFontFamily,fontSize,foregroundColor,bold,italic",
    }
})
```

### Step 3 Verification: Font Check

After the base reset, read back the document and confirm JetBrains Mono applied:

```python
def verify_font(docs_svc, doc_id, expected="JetBrains Mono"):
    doc = docs_svc.documents().get(documentId=doc_id).execute()
    for elem in doc["body"]["content"]:
        para = elem.get("paragraph")
        if not para:
            continue
        for run in para.get("elements", []):
            ts = run.get("textRun", {}).get("textStyle", {})
            wff = ts.get("weightedFontFamily", {})
            actual = wff.get("fontFamily", "")
            if actual and actual != expected:
                raise RuntimeError(
                    f"Font verification failed: expected '{expected}', "
                    f"got '{actual}'. Check Google Fonts availability."
                )
    print(f"Font OK: all runs use '{expected}'")

verify_font(docs_svc, doc_id)
```

**Do not skip this step.** If verification fails, the document will render in Arial.

### Step 4: Apply paragraph and text styles

Same approach as Tufte Classic but with CRT-specific sizes and colors:

```python
# Title: 28pt BRIGHT bold
requests.append({
    "updateTextStyle": {
        "range": {"startIndex": title_start, "endIndex": title_end},
        "textStyle": {
            "weightedFontFamily": {"fontFamily": "JetBrains Mono", "weight": 400},
            "fontSize": {"magnitude": 28, "unit": "PT"},
            "foregroundColor": {"color": {"rgbColor": BRIGHT}},
            "bold": True,
        },
        "fields": "weightedFontFamily,fontSize,foregroundColor,bold",
    }
})

# H1: 22pt BRIGHT bold
# H2: 16pt NORMAL bold, spaceAbove 18pt
# H3: 13pt DIM
# H4: 12pt FAINT italic
# Body: 11pt NORMAL (already set by reset)
```

## Tables

- Header cells: NORMAL color, bold
- Body cells: NORMAL color, weight 400
- No visible borders (use GHOST background for alternating rows if needed)
- 10pt font size in table cells

## Code Blocks

Since Google Docs doesn't support code blocks natively:
- Use GHOST as paragraph background (via table with single cell)
- 9pt font size
- NORMAL text color
- **Important:** Strip all ``` fences from markdown before import — code blocks break the CRT aesthetic with white/gray boxes

## Key Rules

- **ALWAYS set background to NEAR_BLACK** — this is what makes it CRT
- **Color hierarchy is brightness, not hue** — BRIGHT > NORMAL > DIM > FAINT > GHOST
- **Bold on titles and H1/H2 only** — body text is never bold
- **No white text** — even the brightest level is the phosphor color, not white
- **Strip markdown formatting** — remove `#`, `**`, ``` fences, `|` pipes before inserting
- **variant parameter** — when the user specifies C/A/G, swap the entire color palette accordingly
- **This is NOT Tufte Classic** — Tufte Classic has white background and near-black text. CRT inverts this.
