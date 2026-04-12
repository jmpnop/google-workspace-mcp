---
name: gdocs-tufte-classic
description: Creates and formats Google Docs using the Tufte Classic design — JetBrains Mono 400, near-black (#1A1A1A) text on white background, pageless landscape, 54pt margins, heading hierarchy via size only (24/18/14/12pt). Converts ASCII art to SVG diagrams. Use when creating or formatting Google Docs in the clean Tufte style.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Google Docs — Tufte Classic Design System

Create publication-quality Google Docs using the Docs API with monochrome near-black typography, single monospace font, minimal spacing, pageless landscape layout. ASCII diagrams are converted to crisp SVG→PNG images.

## When to use this skill

When the user asks to create, format, or style a Google Doc in "Tufte" or "Tufte Classic" style. This is the light/white background variant. For dark background with colored text, see `gdocs-tufte-crt`.

**Reference:** Create any Google Doc and format it with this pipeline to see the result.

## Prerequisites

- Python with Google API libraries (run via `uv run --project <WORKSPACE_MCP_PROJECT_DIR> python3`, where `<WORKSPACE_MCP_PROJECT_DIR>` is the path to the cloned `google_workspace_mcp` repo)
- OAuth credentials in `~/.google_workspace_mcp/credentials/` (auto-detected — any `*.json` file; set `WORKSPACE_MCP_CREDENTIALS_DIR` to override)
- `rsvg-convert` for SVG→PNG rendering (`brew install librsvg`)

## Font — JetBrains Mono

JetBrains Mono is available on [Google Fonts](https://fonts.google.com/specimen/JetBrains+Mono) and works natively in Google Docs via the API — no local installation required. However, the API silently falls back to Arial if the font name is misspelled or unavailable, so every publishing script **must** verify the font applied correctly after Phase 4.

### Font Verification (mandatory after Phase 4)

```python
def verify_font(docs_svc, doc_id, expected="JetBrains Mono"):
    """Read back the doc and confirm JetBrains Mono applied. Raises if not."""
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
```

Call `verify_font(docs_svc, doc_id)` immediately after Phase 4 completes. If it raises, do NOT proceed — the document will render in Arial and look wrong.

## Design Principles

1. **Single font family** — JetBrains Mono weight 400 throughout. No weight variation except bold on H2.
2. **Monochrome** — near-black `#1A1A1A` (rgb 0.102) for all text. No colored headings, no accent colors.
3. **Heading hierarchy via size** — Title 24pt, H1 18pt, H2 14pt bold, H3/H4 12pt (gray variants).
4. **White background** — no tint, no cream, pure white (default, do NOT set background color).
5. **Pageless landscape** — continuous scroll, no page breaks, landscape orientation.
6. **Minimal spacing** — 3pt spaceBelow on all elements, 24pt spaceAbove on H2 only.
7. **No decoration** — no borders, no rules, no chartjunk. Content speaks for itself.
8. **Diagrams as images** — ASCII art is converted to SVG and rendered as high-res PNG. Never leave box-drawing text.

## Color Palette

```python
INK = {"red": 0.102, "green": 0.102, "blue": 0.102}      # #1A1A1A — all text
H3_GRAY = {"red": 0.263, "green": 0.263, "blue": 0.263}   # Slightly lighter
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
| Table text | 10pt | 400 | INK | |
| Code blocks | 9pt | 400 | INK | light gray background shading |

## Document Setup

```python
PAGE_WIDTH_PT = 792
PAGE_HEIGHT_PT = 612    # Landscape
MARGIN_PT = 54          # All four sides
LINE_SPACING = 115      # Percentage
SPACE_BELOW_PT = 3      # Universal
H2_SPACE_ABOVE_PT = 24
```

## Pipeline Architecture (9 Phases)

The publishing script follows a strict 9-phase pipeline. Each phase must complete before the next begins, because formatting operations depend on stable document indices.

### Phase 1: Create/Update Document

Import markdown via **Drive API** (NOT Docs API insertText). This preserves tables, headings, and structure:

```python
from googleapiclient.http import MediaIoBaseUpload
import io

def create_doc_from_markdown(drive_svc, md_content, title):
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    media = MediaIoBaseUpload(
        io.BytesIO(md_content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=True,
    )
    result = drive_svc.files().create(
        body=file_metadata, media_body=media, fields="id,webViewLink"
    ).execute()
    return result["id"], result.get("webViewLink", "")
```

For **updating** an existing doc: wipe body via `deleteContentRange`, then `files().update()` with markdown media.

### Phase 2: Page Setup

```python
docs_svc.documents().batchUpdate(
    documentId=doc_id,
    body={"requests": [{
        "updateDocumentStyle": {
            "documentStyle": {
                "pageSize": {
                    "width": {"magnitude": 792, "unit": "PT"},
                    "height": {"magnitude": 612, "unit": "PT"},
                },
                "marginLeft": {"magnitude": 54, "unit": "PT"},
                "marginRight": {"magnitude": 54, "unit": "PT"},
                "marginTop": {"magnitude": 54, "unit": "PT"},
                "marginBottom": {"magnitude": 54, "unit": "PT"},
            },
            "fields": "pageSize,marginLeft,marginRight,marginTop,marginBottom",
        }
    }]}
).execute()
```

### Phase 2.5: Post-Table Spacing

Google's markdown import removes blank lines after tables, causing text to stick to table borders. Fix by inserting `\n` after each table's `endIndex` (process in reverse order to preserve indices):

```python
doc = docs_svc.documents().get(documentId=doc_id).execute()
table_ends = sorted(
    (elem["endIndex"] for elem in doc["body"]["content"] if "table" in elem),
    reverse=True,
)
for tend in table_ends:
    docs_svc.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": tend}, "text": "\n"}}]}
    ).execute()
```

### Phase 3: Heading Styles

Match headings extracted from markdown against doc paragraphs. Apply `namedStyleType` (TITLE, HEADING_1, etc.) and spacing:

- Title: namedStyleType=TITLE, spaceBelow 3pt
- H1: namedStyleType=HEADING_1, spaceBelow 3pt
- H2: namedStyleType=HEADING_2, spaceAbove 24pt, spaceBelow 3pt
- H3/H4: same pattern

### Phase 4: Font Formatting

Apply JetBrains Mono 400 and INK color to entire body, then override per heading level:

```python
# Global reset
fmt_text(1, total_length, font_size=12, fg_color=INK, font_family="JetBrains Mono")

# Per heading
# Title: 24pt, H1: 18pt, H2: 14pt bold, H3: 12pt H3_GRAY, H4: 12pt H4_GRAY italic
```

### Phase 4 Verification: Font Check

After applying all font formatting, call `verify_font(docs_svc, doc_id)` to confirm JetBrains Mono is present on every text run. See the Font Verification section above. **Do not skip this step.**

### Phase 4.5: Code Block Styling

Code blocks use zero-width joiner (ZWJ) markers inserted during markdown preprocessing:

**Preprocessing** (before doc import):
```python
# Strip ``` fences, prefix code lines with \u200B{lang}\u200B
# Replace leading spaces with \u00A0 (non-breaking space)
# Add blank line after each code line (paragraph separator)
```

**Styling**: Find paragraphs starting with `\u200B`, apply 9pt font, light gray background shading, then delete the ZWJ markers.

### Phase 5: Table Styling

- Light gray borders (rgb 0.7, 0.7, 0.7), 0.5pt width
- Header row: bold text
- All cells: 10pt font, INK color
- Column widths: calculated from content character count

### Phase 6: Image Pipeline (SVG Diagrams)

**MANDATORY** — see dedicated section below.

### Phase 7: Pageless Mode

```python
docs_svc.documents().batchUpdate(
    documentId=doc_id,
    body={"requests": [{
        "updateDocumentFormat": {
            "documentFormat": {"documentMode": "PAGELESS"},
            "fields": "documentMode",
        }
    }]}
).execute()
```

## Image Pipeline — ASCII Art to SVG Diagrams

**MANDATORY**: Any ASCII art, box-drawing diagrams, or text-based flowcharts in the source markdown MUST be converted to SVG diagrams rendered as high-res PNG images. Never leave ASCII art as plain text in the final Google Doc.

### Detection

Scan markdown for fenced code blocks containing box-drawing characters (`┌`, `─`, `│`, `└`, `▼`, `►`, `→`, `├`, `╔`, `═`, etc.) or structural ASCII art.

### IMAGES Config

Define each diagram with its position and replacement zone:

```python
IMAGES = [
    {
        "filename": "crate_architecture.png",
        "insert_after_heading": ["1. Crate Overview"],
        "width_pt": 700,
        "replace_zone": {
            "type": "fenced_code_block",
            "after_marker": ["## 1. Crate Overview"],
        },
        "svg_generated": True,
    },
]
```

### SVG Design Guidelines (Tufte Classic)

- **Boxes**: `rx="3"` rounded corners, stroke="#1A1A1A", stroke-width="1.5", fill="white" or fill="#F8F8F8"
- **Arrows**: stroke="#1A1A1A", stroke-width="1.5", marker-end with filled arrowhead
- **Text**: font-family="JetBrains Mono", font-size="11-14", fill="#1A1A1A"
- **Labels**: font-size="9-10", fill="#434343" (slightly lighter for secondary info)
- **Layout**: generous spacing, align to grid, minimize crossing lines
- **No decoration**: no drop shadows, no gradients, no color fills

### Render SVG to PNG

```python
import subprocess
def render_svg(svg_content, name, output_dir):
    svg_path = output_dir / f"{name}.svg"
    png_path = output_dir / f"{name}.png"
    svg_path.write_text(svg_content)
    subprocess.run(["rsvg-convert", str(svg_path), "-w", "3600", "-o", str(png_path)], check=True)
    return png_path
```

### Strip ASCII Zones from Markdown

Before importing markdown, remove the code blocks that contain ASCII art (they're replaced by images). Process in reverse order to preserve line numbers:

```python
def strip_image_replacement_zones(md_text, images):
    lines = md_text.split("\n")
    for img in reversed(images):
        zone = img.get("replace_zone")
        if not zone:
            continue
        markers = zone["after_marker"]
        if isinstance(markers, str):
            markers = [markers]
        marker_idx = None
        for i, line in enumerate(lines):
            if line.strip() in markers:
                marker_idx = i
                break
        if marker_idx is None:
            continue
        if zone["type"] == "fenced_code_block":
            fence_start = fence_end = None
            for j in range(marker_idx + 1, len(lines)):
                if lines[j].strip().startswith("```"):
                    if fence_start is None:
                        fence_start = j
                    else:
                        fence_end = j
                        break
            if fence_start is not None and fence_end is not None:
                lines = lines[:fence_start] + lines[fence_end + 1:]
    return "\n".join(lines)
```

### Upload and Insert Images

```python
def upload_image(drive_svc, filepath):
    meta = {"name": filepath.name, "mimeType": "image/png"}
    media = MediaFileUpload(str(filepath), mimetype="image/png")
    f = drive_svc.files().create(body=meta, media_body=media, fields="id").execute()
    drive_svc.permissions().create(
        fileId=f["id"], body={"type": "anyone", "role": "reader"}
    ).execute()
    return f["id"]

def insert_images(docs_svc, drive_svc, doc_id, images, image_dir):
    for img_spec in images:
        filepath = image_dir / img_spec["filename"]
        fid = upload_image(drive_svc, filepath)
        image_uri = f"https://drive.google.com/uc?id={fid}"
        # Find target heading, insert newline, then insertInlineImage
        # Re-fetch doc between each image (indices shift)
```

## Infrastructure Patterns

### Rate-Limit Retry

Google Docs API rate-limits on large documents (~batch 8-10). All API calls must use retry logic:

```python
def _retry_api(fn, label="API call", retries=5):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT" in str(e):
                wait = 15 * (attempt + 1)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"{label}: failed after {retries} retries")
```

### Batch Execution

Large formatting passes produce hundreds of operations. Batch them in groups of 50:

```python
def batch_execute(service, doc_id, requests, label="", batch_size=50):
    for i in range(0, len(requests), batch_size):
        batch = requests[i : i + batch_size]
        # Execute with retry logic
```

### Credential Boilerplate

```python
import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CRED_DIR = Path(os.environ.get("WORKSPACE_MCP_CREDENTIALS_DIR",
           Path.home() / ".google_workspace_mcp/credentials"))

def get_services():
    cred_files = sorted(CRED_DIR.glob("*.json"))
    if not cred_files:
        raise FileNotFoundError(f"No credential files found in {CRED_DIR}")
    cred_path = cred_files[0]
    with open(cred_path) as f:
        cred_data = json.load(f)
    creds = Credentials(
        token=cred_data.get("token"),
        refresh_token=cred_data.get("refresh_token"),
        token_uri=cred_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=cred_data.get("client_id"),
        client_secret=cred_data.get("client_secret"),
        scopes=cred_data.get("scopes"),
    )
    if creds.expired:
        creds.refresh(Request())
    docs = build("docs", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    return docs, drive
```

### Request Builders

```python
def fmt_text(start, end, font_size=None, bold=None, italic=None, underline=None,
             fg_color=None, font_family="JetBrains Mono"):
    style, fields = {}, []
    if font_family:
        style["weightedFontFamily"] = {"fontFamily": font_family, "weight": 400}
        fields.append("weightedFontFamily")
    if font_size is not None:
        style["fontSize"] = {"magnitude": font_size, "unit": "PT"}
        fields.append("fontSize")
    if bold is not None:
        style["bold"] = bold; fields.append("bold")
    if italic is not None:
        style["italic"] = italic; fields.append("italic")
    if underline is not None:
        style["underline"] = underline; fields.append("underline")
    if fg_color:
        style["foregroundColor"] = {"color": {"rgbColor": fg_color}}
        fields.append("foregroundColor")
    return {"updateTextStyle": {
        "range": {"startIndex": start, "endIndex": end},
        "textStyle": style, "fields": ",".join(fields),
    }}

def fmt_heading(start, end, level, space_above=0, space_below=3):
    named = "NORMAL_TEXT" if level == 0 else f"HEADING_{level}"
    style = {"namedStyleType": named}
    fields = ["namedStyleType"]
    if space_above:
        style["spaceAbove"] = {"magnitude": space_above, "unit": "PT"}
        fields.append("spaceAbove")
    if space_below:
        style["spaceBelow"] = {"magnitude": space_below, "unit": "PT"}
        fields.append("spaceBelow")
    return {"updateParagraphStyle": {
        "range": {"startIndex": start, "endIndex": end},
        "paragraphStyle": style, "fields": ",".join(fields),
    }}
```

## API Gotchas (Hard-Won)

1. **`useCustomHeaderFooterMargins`** — REJECTED by the API. Do NOT include in updateDocumentStyle. Will cause HttpError 400.
2. **`flipPageOrientation`** — Also rejected. Omit from updateDocumentStyle fields.
3. **Pageless mode** — Use `updateDocumentFormat` with `documentMode: "PAGELESS"`, NOT page size tricks.
4. **Table indices shift** — After inserting text (Phase 2.5) or images (Phase 6), re-fetch the doc to get fresh indices.
5. **Rate limiting** — Hits around batch 8-10 on large docs. Always use retry with 15s incremental backoff.
6. **Markdown import** — Use Drive API with `mimetype="text/markdown"`, not Docs API insertText. This auto-creates tables, headings, lists.
7. **Code fences** — Strip ``` fences BEFORE import (they cause rendering issues). Use ZWJ markers (\u200B) to identify code paragraphs in the doc.
8. **Non-breaking spaces** — Use \u00A0 for code indentation (regular spaces get collapsed by Docs).
9. **Horizontal rules** — Strip `---` lines (they create unwanted horizontal rules in Docs).
10. **Doc ID reuse** — Support `--doc-id` flag to update existing docs in-place instead of creating new ones every time.

## Tables

- Header row: same font, same size, bold text
- Body rows: normal weight
- Light gray borders (0.7, 0.7, 0.7), 0.5pt
- No cell fills — keep the monochrome aesthetic
- Column widths auto-calculated from content character count

## Key Rules

- **JetBrains Mono 400 only** — never EB Garamond, never serif, never any other font
- **Never use colored text** — all text is INK (#1A1A1A) except H3 (0.263 gray) and H4 (0.4 gray)
- **Never set background color** — white is the default
- **Bold only on H2** — no other bold usage in the document structure
- **Strip markdown formatting marks** — remove `#`, `**`, `|` table pipes, etc. before inserting text
- **spaceBelow 3pt everywhere** — universal spacing rule
- **Convert all ASCII art to SVG images** — never leave box-drawing diagrams as text in the final doc
- **Always use Python + Google Docs API** — not MCP tools, not manual formatting
- **Run via:** `uv run --project <WORKSPACE_MCP_PROJECT_DIR> python3 <script>` (use the path to the cloned `google_workspace_mcp` repo)
