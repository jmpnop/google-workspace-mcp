"""
Tufte Publishing Pipeline

Full 9-phase pipeline for publishing markdown to Google Docs
with Tufte Classic or CRT styling. All functions are async and
accept pre-authenticated service objects (injected by MCP auth decorators).
"""

import asyncio
import hashlib
import io
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.http import MediaIoBaseUpload

from gdocs.docs_helpers import create_insert_image_request
from gdocs.docs_svg import _svg_to_png_bytes
from gdocs.tufte_cache import TuftePubCache
from gdocs.tufte_styles import (
    TufteStyle,
    fmt_text,
    fmt_heading,
    get_title_color,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Infrastructure helpers
# ---------------------------------------------------------------------------


def _retry_api(fn, label: str = "API call", retries: int = 5):
    """Retry a synchronous Google API call with backoff on rate limits."""
    for attempt in range(retries):
        try:
            return fn()
        except (BrokenPipeError, ConnectionError, ConnectionResetError) as exc:
            wait = 5 * (attempt + 1)
            logger.warning(f"[tufte] {label}: connection error ({exc}), retrying in {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RATE_LIMIT" in msg or "rateLimitExceeded" in msg:
                wait = 15 * (attempt + 1)
                logger.warning(f"[tufte] {label}: rate-limited, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"[tufte] {label}: failed after {retries} retries")


async def _batch_execute(
    docs_svc: Any,
    doc_id: str,
    requests: List[dict],
    label: str = "",
    batch_size: int = 50,
) -> None:
    """Execute Docs API batchUpdate in batches with retry."""
    for i in range(0, len(requests), batch_size):
        batch = requests[i : i + batch_size]
        tag = f"{label} [{i}..{i + len(batch)}]" if label else f"batch [{i}..{i + len(batch)}]"
        await asyncio.to_thread(
            _retry_api,
            lambda b=batch: docs_svc.documents()
            .batchUpdate(documentId=doc_id, body={"requests": b})
            .execute(),
            tag,
        )


def _get_doc_length(doc: dict) -> int:
    """Return the end index of the document body."""
    content = doc.get("body", {}).get("content", [])
    if not content:
        return 1
    return content[-1].get("endIndex", 1)


# ---------------------------------------------------------------------------
# Markdown preprocessing
# ---------------------------------------------------------------------------

_BOX_CHARS = set("┌┐└┘─│├┤┬┴┼═║╔╗╚╝╠╣╦╩╬▼►▲◄→←↓↑")

ZWJ = "\u200B"
NBSP = "\u00A0"


def _detect_ascii_art_blocks(md_text: str) -> List[Tuple[int, int, str]]:
    """Find fenced code blocks that contain box-drawing / ASCII art.

    Returns list of (start_line, end_line, content) tuples.
    """
    lines = md_text.split("\n")
    blocks = []
    fence_start = None
    fence_content_lines: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            if fence_start is None:
                fence_start = i
                fence_content_lines = []
            else:
                content = "\n".join(fence_content_lines)
                if any(ch in content for ch in _BOX_CHARS):
                    blocks.append((fence_start, i, content))
                fence_start = None
                fence_content_lines = []
        elif fence_start is not None:
            fence_content_lines.append(line)

    return blocks


def _strip_ascii_art_zones(md_text: str, blocks: List[Tuple[int, int, str]]) -> str:
    """Remove ASCII art fenced blocks from markdown (reverse order to preserve indices)."""
    lines = md_text.split("\n")
    for start, end, _ in reversed(blocks):
        lines = lines[:start] + lines[end + 1 :]
    return "\n".join(lines)


def _preprocess_code_blocks(md_text: str) -> str:
    """Replace ``` fences with ZWJ markers and convert leading spaces to NBSP.

    Fenced code blocks that contain ASCII art are left alone (they'll be
    stripped separately and replaced with images).
    """
    lines = md_text.split("\n")
    result = []
    in_fence = False
    fence_lang = ""
    is_ascii_art = False
    fence_lines: list[str] = []
    fence_start_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence:
                in_fence = True
                fence_lang = stripped[3:].strip()
                fence_lines = []
                fence_start_idx = i
                is_ascii_art = False
            else:
                # End of fence — check if it's ASCII art
                content = "\n".join(fence_lines)
                if any(ch in content for ch in _BOX_CHARS):
                    # Keep ASCII art fences as-is (they'll be stripped later)
                    result.append(f"```{fence_lang}")
                    result.extend(fence_lines)
                    result.append("```")
                else:
                    # Convert to ZWJ-marked code lines
                    for code_line in fence_lines:
                        converted = code_line.replace(" ", NBSP)
                        result.append(f"{ZWJ}{fence_lang}{ZWJ}{converted}")
                        result.append("")  # Blank line = paragraph separator
                in_fence = False
                fence_lang = ""
                fence_lines = []
        elif in_fence:
            fence_lines.append(line)
            if any(ch in line for ch in _BOX_CHARS):
                is_ascii_art = True
        else:
            # Strip horizontal rules (--- on its own line)
            if re.match(r"^-{3,}\s*$", stripped):
                continue
            result.append(line)

    return "\n".join(result)


def _is_table_separator(line: str) -> bool:
    """Return True if *line* is a markdown table separator row (e.g. |---|---|)."""
    stripped = line.strip()
    return bool(re.match(r"^\|[\s\-:| ]+\|$", stripped)) and "---" in stripped


def _preprocess_tables(md_text: str) -> str:
    """Fix markdown tables so Google Drive's markdown importer recognises them.

    Google Drive's ``text/markdown`` import is undocumented and has at least
    two known parser limitations that cause tables to render as raw ASCII
    pipe-text instead of native Google Docs tables:

    1. **Missing blank line before table.**  When a table header row
       immediately follows a paragraph line (no intervening blank line),
       Google's parser treats the table as paragraph continuation.
       Standard GFM allows this, but Google does not.  Fix: insert a
       blank line before the header row.

    2. **Non-ASCII characters in the header row.**  If the header row
       (the first ``| … |`` line) contains non-ASCII characters such as
       en-dash (U+2013), Google's parser fails to recognise the row as a
       table header.  Fix: replace common typographic characters with
       their ASCII equivalents in header rows only (data rows are left
       untouched).
    """
    _HEADER_REPLACEMENTS = {
        "\u2013": "-",   # en-dash  → hyphen
        "\u2014": "-",   # em-dash  → hyphen
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201C": '"',   # left double quote
        "\u201D": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00D7": "x",   # multiplication sign
    }

    lines = md_text.split("\n")
    result: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect a table header: current line is ``| … |`` and the
        # very next line is a separator row ``|---|---|…|``.
        is_header = (
            stripped.startswith("|")
            and stripped.endswith("|")
            and i + 1 < len(lines)
            and _is_table_separator(lines[i + 1])
        )

        if is_header:
            # --- Fix 1: ensure a blank line precedes the header --------
            prev = result[-1].strip() if result else ""
            if prev != "" and not re.match(r"^#{1,6}\s", prev):
                result.append("")

            # --- Fix 2: normalise non-ASCII chars in the header row ----
            fixed = stripped
            for orig, repl in _HEADER_REPLACEMENTS.items():
                if orig in fixed:
                    fixed = fixed.replace(orig, repl)
            if fixed != stripped:
                logger.debug(
                    "[tufte] _preprocess_tables: normalised header at line %d", i + 1
                )
            result.append(fixed)
        else:
            result.append(line)

    return "\n".join(result)


def _extract_headings(md_text: str) -> List[Tuple[int, str]]:
    """Parse markdown headings. Returns [(level, text), ...]."""
    headings = []
    for line in md_text.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append((level, text))
    return headings


# ---------------------------------------------------------------------------
# Phase 1: Create or update document
# ---------------------------------------------------------------------------


async def _phase1_create_or_update(
    drive_svc: Any,
    docs_svc: Any,
    md_content: str,
    title: str,
    cache: TuftePubCache,
    explicit_doc_id: str = "",
) -> Tuple[str, str]:
    """Create or update a Google Doc from markdown via Drive API.

    Returns (doc_id, web_view_link).
    """
    doc_id = explicit_doc_id or cache.get_doc_id(title)

    media = MediaIoBaseUpload(
        io.BytesIO(md_content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=True,
    )

    if doc_id:
        # Update existing doc: wipe body first, then upload new content
        logger.info(f"[tufte] Phase 1: Updating existing doc {doc_id}")

        # Delete all body content
        doc = await asyncio.to_thread(
            _retry_api,
            lambda: docs_svc.documents().get(documentId=doc_id).execute(),
            "Phase 1 get doc",
        )
        end_idx = _get_doc_length(doc)
        if end_idx > 2:
            await asyncio.to_thread(
                _retry_api,
                lambda: docs_svc.documents()
                .batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "deleteContentRange": {
                                    "range": {
                                        "startIndex": 1,
                                        "endIndex": end_idx - 1,
                                    }
                                }
                            }
                        ]
                    },
                )
                .execute(),
                "Phase 1 delete body",
            )

        # Upload new markdown content
        update_metadata = {
            "mimeType": "application/vnd.google-apps.document",
        }
        await asyncio.to_thread(
            _retry_api,
            lambda: drive_svc.files()
            .update(fileId=doc_id, body=update_metadata, media_body=media)
            .execute(),
            "Phase 1 update file",
        )

        file_info = await asyncio.to_thread(
            _retry_api,
            lambda: drive_svc.files()
            .get(fileId=doc_id, fields="webViewLink")
            .execute(),
            "Phase 1 get link",
        )
        link = file_info.get("webViewLink", f"https://docs.google.com/document/d/{doc_id}/edit")
    else:
        # Create new doc
        logger.info(f"[tufte] Phase 1: Creating new doc '{title}'")
        file_metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
        }
        result = await asyncio.to_thread(
            _retry_api,
            lambda: drive_svc.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute(),
            "Phase 1 create file",
        )
        doc_id = result["id"]
        link = result.get("webViewLink", f"https://docs.google.com/document/d/{doc_id}/edit")

    cache.set_doc_id(title, doc_id)
    logger.info(f"[tufte] Phase 1 complete: doc_id={doc_id}")
    return doc_id, link


# ---------------------------------------------------------------------------
# Phase 2: Page setup
# ---------------------------------------------------------------------------


async def _phase2_page_setup(docs_svc: Any, doc_id: str, style: TufteStyle) -> None:
    """Set page size, margins, and optional background color."""
    logger.info("[tufte] Phase 2: Page setup")

    doc_style: Dict[str, Any] = {
        "pageSize": {
            "width": {"magnitude": style.page_width_pt, "unit": "PT"},
            "height": {"magnitude": style.page_height_pt, "unit": "PT"},
        },
        "marginLeft": {"magnitude": style.margin_left_pt, "unit": "PT"},
        "marginRight": {"magnitude": style.margin_right_pt, "unit": "PT"},
        "marginTop": {"magnitude": style.margin_top_pt, "unit": "PT"},
        "marginBottom": {"magnitude": style.margin_bottom_pt, "unit": "PT"},
    }
    fields = "pageSize,marginLeft,marginRight,marginTop,marginBottom"

    if style.background is not None:
        doc_style["background"] = {"color": {"color": {"rgbColor": style.background}}}
        fields += ",background"

    await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents()
        .batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "updateDocumentStyle": {
                            "documentStyle": doc_style,
                            "fields": fields,
                        }
                    }
                ]
            },
        )
        .execute(),
        "Phase 2 page setup",
    )


# ---------------------------------------------------------------------------
# Phase 2.5: Post-table spacing
# ---------------------------------------------------------------------------


async def _phase2_5_post_table_spacing(docs_svc: Any, doc_id: str) -> None:
    """Insert newline after each table to prevent text sticking to table borders."""
    logger.info("[tufte] Phase 2.5: Post-table spacing")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 2.5 get doc",
    )

    table_ends = sorted(
        (elem["endIndex"] for elem in doc["body"]["content"] if "table" in elem),
        reverse=True,
    )

    for tend in table_ends:
        await asyncio.to_thread(
            _retry_api,
            lambda t=tend: docs_svc.documents()
            .batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {"insertText": {"location": {"index": t}, "text": "\n"}}
                    ]
                },
            )
            .execute(),
            "Phase 2.5 insert newline",
        )


# ---------------------------------------------------------------------------
# Phase 3: Heading styles
# ---------------------------------------------------------------------------


async def _phase3_heading_styles(
    docs_svc: Any,
    doc_id: str,
    md_text: str,
    style: TufteStyle,
) -> None:
    """Match headings from markdown to doc paragraphs and apply named styles."""
    logger.info("[tufte] Phase 3: Heading styles")

    headings = _extract_headings(md_text)
    if not headings:
        logger.info("[tufte] Phase 3: No headings found, skipping")
        return

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 3 get doc",
    )

    requests = []
    heading_idx = 0
    is_first_heading = True

    for elem in doc["body"]["content"]:
        if heading_idx >= len(headings):
            break
        para = elem.get("paragraph")
        if not para:
            continue

        # Extract paragraph text
        para_text = ""
        for run in para.get("elements", []):
            tr = run.get("textRun")
            if tr:
                para_text += tr.get("content", "")
        para_text = para_text.strip()

        level, heading_text = headings[heading_idx]

        # Fuzzy match: the imported doc may strip some markdown formatting
        if heading_text in para_text or para_text in heading_text or _normalize(para_text) == _normalize(heading_text):
            start = elem["startIndex"]
            end = elem["endIndex"]

            if is_first_heading and level == 1:
                requests.append(fmt_heading(start, end, -1, space_below=style.space_below_pt))
                is_first_heading = False
            elif level == 1:
                requests.append(
                    fmt_heading(start, end, 1, space_above=style.h1_space_above_pt, space_below=style.h1_space_below_pt)
                )
            elif level == 2:
                requests.append(
                    fmt_heading(start, end, 2, space_above=style.h2_space_above_pt, space_below=style.h2_space_below_pt)
                )
            elif level == 3:
                requests.append(
                    fmt_heading(start, end, 3, space_above=style.h3_space_above_pt, space_below=style.h3_space_below_pt)
                )
            elif level == 4:
                requests.append(
                    fmt_heading(start, end, 4, space_above=style.h4_space_above_pt, space_below=style.h4_space_below_pt)
                )
            else:
                requests.append(fmt_heading(start, end, min(level, 6), space_below=style.space_below_pt))

            heading_idx += 1

    if requests:
        await _batch_execute(docs_svc, doc_id, requests, "Phase 3 headings")


def _normalize(text: str) -> str:
    """Normalize heading text for fuzzy matching."""
    # Replace common Unicode arrows and symbols with ASCII equivalents
    # so that e.g. "→" (U+2192) matches "->" after Google's markdown import.
    _unicode_to_ascii = {
        "\u2192": "->",   # → rightwards arrow
        "\u2190": "<-",   # ← leftwards arrow
        "\u2191": "^",    # ↑ upwards arrow
        "\u2193": "v",    # ↓ downwards arrow
        "\u2014": "--",   # — em dash
        "\u2013": "-",    # – en dash
    }
    for uni, ascii_eq in _unicode_to_ascii.items():
        text = text.replace(uni, ascii_eq)
    return re.sub(r"[#*_`\s]+", "", text).lower()


# ---------------------------------------------------------------------------
# Phase 4: Font formatting
# ---------------------------------------------------------------------------


async def _phase4_font_formatting(docs_svc: Any, doc_id: str, style: TufteStyle) -> None:
    """Apply global font reset then per-heading text styles."""
    logger.info("[tufte] Phase 4: Font formatting")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 4 get doc",
    )
    total_length = _get_doc_length(doc)
    if total_length <= 2:
        return

    title_color = get_title_color(style)

    # Global reset — body size + ink color
    requests = [
        fmt_text(1, total_length - 1, style, font_size=style.body_size, bold=False, italic=False)
    ]

    # Per-heading overrides
    for elem in doc["body"]["content"]:
        para = elem.get("paragraph")
        if not para:
            continue
        named = para.get("paragraphStyle", {}).get("namedStyleType", "")
        start = elem["startIndex"]
        end = elem["endIndex"]

        if named == "TITLE":
            requests.append(
                fmt_text(start, end, style, font_size=style.title_size, bold=style.title_bold, fg_color=title_color)
            )
        elif named == "HEADING_1":
            requests.append(
                fmt_text(start, end, style, font_size=style.h1_size, bold=style.h1_bold, fg_color=title_color)
            )
        elif named == "HEADING_2":
            requests.append(
                fmt_text(start, end, style, font_size=style.h2_size, bold=style.h2_bold, fg_color=style.ink)
            )
        elif named == "HEADING_3":
            requests.append(
                fmt_text(start, end, style, font_size=style.h3_size, fg_color=style.h3_color)
            )
        elif named == "HEADING_4":
            requests.append(
                fmt_text(start, end, style, font_size=style.h4_size, italic=style.h4_italic, fg_color=style.h4_color)
            )

    if requests:
        await _batch_execute(docs_svc, doc_id, requests, "Phase 4 font")


async def _phase4_verify_font(docs_svc: Any, doc_id: str, expected: str = "JetBrains Mono") -> None:
    """Read back the doc and verify JetBrains Mono applied on all text runs."""
    logger.info("[tufte] Phase 4 verification: Checking font")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 4 verify get doc",
    )

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

    logger.info(f"[tufte] Font OK: all runs use '{expected}'")


# ---------------------------------------------------------------------------
# Phase 4.5: Code block styling
# ---------------------------------------------------------------------------


async def _phase4_5_code_blocks(docs_svc: Any, doc_id: str, style: TufteStyle) -> None:
    """Style ZWJ-marked code paragraphs and remove ZWJ markers."""
    logger.info("[tufte] Phase 4.5: Code block styling")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 4.5 get doc",
    )

    style_requests = []
    delete_requests = []  # ZWJ marker deletions (process in reverse)

    for elem in doc["body"]["content"]:
        para = elem.get("paragraph")
        if not para:
            continue

        # Check if paragraph starts with ZWJ
        elements = para.get("elements", [])
        if not elements:
            continue

        first_text = elements[0].get("textRun", {}).get("content", "")
        if not first_text.startswith(ZWJ):
            continue

        start = elem["startIndex"]
        end = elem["endIndex"]

        # Apply code styling: smaller font, code_bg background
        style_requests.append(
            fmt_text(start, end, style, font_size=style.code_size, bg_color=style.code_bg)
        )

        # Find and mark ZWJ markers for deletion
        # Pattern: ZWJ + lang + ZWJ at the start of the line
        content = first_text
        second_zwj = content.find(ZWJ, 1)
        if second_zwj >= 0:
            # Delete from start to just after the second ZWJ
            marker_end = start + second_zwj + 1
            delete_requests.append((start, marker_end))

    if style_requests:
        await _batch_execute(docs_svc, doc_id, style_requests, "Phase 4.5 code style")

    # Delete ZWJ markers in reverse order to preserve indices
    if delete_requests:
        for del_start, del_end in sorted(delete_requests, reverse=True):
            await asyncio.to_thread(
                _retry_api,
                lambda s=del_start, e=del_end: docs_svc.documents()
                .batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {"deleteContentRange": {"range": {"startIndex": s, "endIndex": e}}}
                        ]
                    },
                )
                .execute(),
                "Phase 4.5 delete ZWJ",
            )


# ---------------------------------------------------------------------------
# Phase 5: Table styling
# ---------------------------------------------------------------------------


async def _phase5_table_styling(docs_svc: Any, doc_id: str, style: TufteStyle) -> None:
    """Apply Tufte table styling: no vertical rules, subtle horizontal rules,
    shaded header row, proper cell padding, and per-row text styling."""
    logger.info("[tufte] Phase 5: Table styling")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 5 get doc",
    )

    requests = []

    no_border = {
        "width": {"magnitude": 0, "unit": "PT"},
        "dashStyle": "SOLID",
        "color": {"color": {"rgbColor": {"red": 0, "green": 0, "blue": 0}}},
    }

    h_rule = {
        "width": {"magnitude": style.table_border_width, "unit": "PT"},
        "dashStyle": "SOLID",
        "color": {"color": {"rgbColor": style.table_border_color}},
    } if style.table_border_width > 0 else no_border

    pad_h = {"magnitude": style.table_cell_pad_h_pt, "unit": "PT"}
    pad_v = {"magnitude": style.table_cell_pad_v_pt, "unit": "PT"}

    for elem in doc["body"]["content"]:
        table = elem.get("table")
        if not table:
            continue

        table_start = elem["startIndex"]
        rows = table.get("tableRows", [])
        if not rows:
            continue

        num_rows = len(rows)
        num_cols = len(rows[0].get("tableCells", []))

        # Step 1: Reset all cells — no borders, uniform padding
        base_cell_style = {
            "borderTop": no_border,
            "borderBottom": no_border,
            "borderLeft": no_border,
            "borderRight": no_border,
            "paddingLeft": pad_h,
            "paddingRight": pad_h,
            "paddingTop": pad_v,
            "paddingBottom": pad_v,
        }
        requests.append({
            "updateTableCellStyle": {
                "tableStartLocation": {"index": table_start},
                "tableCellStyle": base_cell_style,
                "fields": "borderTop,borderBottom,borderLeft,borderRight,paddingLeft,paddingRight,paddingTop,paddingBottom",
            }
        })

        # Step 2: Header row — top and bottom horizontal rules + background
        header_style = {
            "borderTop": h_rule,
            "borderBottom": h_rule,
        }
        header_fields = ["borderTop", "borderBottom"]
        if style.table_header_bg:
            header_style["backgroundColor"] = {"color": {"rgbColor": style.table_header_bg}}
            header_fields.append("backgroundColor")

        requests.append({
            "updateTableCellStyle": {
                "tableRange": {
                    "tableCellLocation": {
                        "tableStartLocation": {"index": table_start},
                        "rowIndex": 0,
                        "columnIndex": 0,
                    },
                    "rowSpan": 1,
                    "columnSpan": num_cols,
                },
                "tableCellStyle": header_style,
                "fields": ",".join(header_fields),
            }
        })

        # Step 3: Last row — bottom horizontal rule
        if num_rows > 1:
            requests.append({
                "updateTableCellStyle": {
                    "tableRange": {
                        "tableCellLocation": {
                            "tableStartLocation": {"index": table_start},
                            "rowIndex": num_rows - 1,
                            "columnIndex": 0,
                        },
                        "rowSpan": 1,
                        "columnSpan": num_cols,
                    },
                    "tableCellStyle": {"borderBottom": h_rule},
                    "fields": "borderBottom",
                }
            })

        # Step 4: Style text in each row
        for row_idx, row in enumerate(rows):
            is_header = row_idx == 0
            for cell in row.get("tableCells", []):
                for cell_elem in cell.get("content", []):
                    cell_para = cell_elem.get("paragraph")
                    if not cell_para:
                        continue
                    cell_start = cell_elem["startIndex"]
                    cell_end = cell_elem["endIndex"]

                    text_color = style.ink if is_header else (style.table_data_color or style.ink)
                    requests.append(
                        fmt_text(
                            cell_start,
                            cell_end,
                            style,
                            font_size=style.body_size,
                            bold=is_header,
                            fg_color=text_color,
                        )
                    )

    if requests:
        await _batch_execute(docs_svc, doc_id, requests, "Phase 5 tables")


# ---------------------------------------------------------------------------
# Phase 5.5: Inline bold markers in table cells
# ---------------------------------------------------------------------------

_BOLD_MARKER_RE = re.compile(r"\*\*(.+?)\*\*")


async def _phase5_5_table_inline_bold(
    docs_svc: Any, doc_id: str, style: TufteStyle
) -> None:
    """Convert literal ``**text**`` markers in table cells to bold formatting.

    Google Drive's markdown importer does not process inline bold syntax
    inside table cells, so the raw ``**`` asterisks survive into the
    document.  This phase scans every table cell paragraph, locates
    ``**…**`` patterns, deletes the marker characters, and applies bold
    to the enclosed text.

    Deletions are applied one-by-one from highest index to lowest so that
    earlier indices remain valid.
    """
    logger.info("[tufte] Phase 5.5: Table inline bold markers")

    doc = await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents().get(documentId=doc_id).execute(),
        "Phase 5.5 get doc",
    )

    # Collect bold regions and marker positions across all tables.
    # Each entry: (marker_start, marker_len, bold_start, bold_end)
    #   where marker positions are the absolute doc indices of the ``**``.
    bold_regions: list[tuple[int, int]] = []      # (start, end) of text to bold
    delete_ranges: list[tuple[int, int]] = []     # (start, end) of ``**`` to delete

    for elem in doc["body"]["content"]:
        table = elem.get("table")
        if not table:
            continue

        for row in table.get("tableRows", []):
            for cell in row.get("tableCells", []):
                for cell_elem in cell.get("content", []):
                    cell_para = cell_elem.get("paragraph")
                    if not cell_para:
                        continue

                    # Reconstruct the paragraph's plain text and map each
                    # character position back to its absolute document index.
                    elements = cell_para.get("elements", [])
                    full_text = ""
                    index_map: list[int] = []  # index_map[i] = doc index of char i

                    for run_elem in elements:
                        tr = run_elem.get("textRun")
                        if not tr:
                            continue
                        content = tr.get("content", "")
                        run_start = run_elem["startIndex"]
                        for j, _ in enumerate(content):
                            index_map.append(run_start + j)
                        full_text += content

                    if "**" not in full_text:
                        continue

                    # Find all **…** patterns
                    for m in _BOLD_MARKER_RE.finditer(full_text):
                        # m.start() = position of first '*' of opening **
                        # m.end()   = position after last '*' of closing **
                        open_start = m.start()       # first * of opening **
                        open_end = m.start() + 2     # after opening **
                        close_start = m.end() - 2    # first * of closing **
                        close_end = m.end()          # after closing **

                        # Absolute doc indices for the opening **
                        del_open_start = index_map[open_start]
                        del_open_end = index_map[open_end - 1] + 1

                        # Absolute doc indices for the closing **
                        del_close_start = index_map[close_start]
                        del_close_end = index_map[close_end - 1] + 1

                        # Bold region: the text between the markers (before deletion)
                        bold_start = del_open_end       # right after opening **
                        bold_end = del_close_start      # right before closing **

                        if bold_end > bold_start:
                            bold_regions.append((bold_start, bold_end))

                        # Record deletions (closing first so we process end→start)
                        delete_ranges.append((del_close_start, del_close_end))
                        delete_ranges.append((del_open_start, del_open_end))

    if not bold_regions and not delete_ranges:
        logger.info("[tufte] Phase 5.5: No bold markers found in tables")
        return

    logger.info(
        "[tufte] Phase 5.5: Found %d bold region(s), %d marker deletion(s)",
        len(bold_regions),
        len(delete_ranges),
    )

    # Step 1: Apply bold styling to the regions (non-destructive, indices still valid)
    if bold_regions:
        bold_requests = []
        for b_start, b_end in bold_regions:
            bold_requests.append({
                "updateTextStyle": {
                    "range": {"startIndex": b_start, "endIndex": b_end},
                    "textStyle": {"bold": True},
                    "fields": "bold",
                }
            })
        await _batch_execute(docs_svc, doc_id, bold_requests, "Phase 5.5 bold style")

    # Step 2: Delete ** markers from end to start (one at a time)
    if delete_ranges:
        for del_start, del_end in sorted(delete_ranges, key=lambda r: r[0], reverse=True):
            await asyncio.to_thread(
                _retry_api,
                lambda s=del_start, e=del_end: docs_svc.documents()
                .batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "deleteContentRange": {
                                    "range": {"startIndex": s, "endIndex": e}
                                }
                            }
                        ]
                    },
                )
                .execute(),
                "Phase 5.5 delete bold marker",
            )


# ---------------------------------------------------------------------------
# Phase 6: Image pipeline (ASCII art -> SVG -> PNG -> Drive -> Doc)
# ---------------------------------------------------------------------------


async def _phase6_images(
    docs_svc: Any,
    drive_svc: Any,
    doc_id: str,
    original_md: str,
    style: TufteStyle,
    cache: TuftePubCache,
) -> None:
    """Detect ASCII art blocks in the original markdown, render to SVG/PNG,
    upload to Drive (with caching), and insert into the document."""
    logger.info("[tufte] Phase 6: Image pipeline")

    art_blocks = _detect_ascii_art_blocks(original_md)
    if not art_blocks:
        logger.info("[tufte] Phase 6: No ASCII art blocks found, skipping")
        return

    # For each ASCII art block, we need to:
    # 1. Generate an SVG representation
    # 2. Convert SVG -> PNG via rsvg-convert
    # 3. Upload to Drive (or use cached)
    # 4. Insert into the doc at the right position

    # We need to find where the ASCII art was in the original markdown
    # and locate the corresponding position in the doc.
    # Since we stripped the ASCII art before import, we look for the
    # heading that preceded each block.

    md_lines = original_md.split("\n")

    for start_line, end_line, art_content in art_blocks:
        # Find the heading that precedes this block
        preceding_heading = None
        for i in range(start_line - 1, -1, -1):
            m = re.match(r"^(#{1,6})\s+(.+)$", md_lines[i].strip())
            if m:
                preceding_heading = m.group(2).strip()
                break

        if not preceding_heading:
            logger.warning(f"[tufte] Phase 6: No preceding heading found for art block at line {start_line}")
            continue

        # Check image cache
        art_hash = hashlib.sha256(art_content.encode("utf-8")).hexdigest()
        cached_file_id = cache.get_image(art_hash)

        if cached_file_id:
            # Verify the file still exists on Drive
            try:
                await asyncio.to_thread(
                    drive_svc.files().get(fileId=cached_file_id, fields="id").execute
                )
                file_id = cached_file_id
                logger.info(f"[tufte] Phase 6: Using cached image for '{preceding_heading}': {file_id}")
            except Exception:
                logger.info(f"[tufte] Phase 6: Cached image {cached_file_id} no longer exists, re-uploading")
                cached_file_id = None

        if not cached_file_id:
            # The ASCII art content itself is box-drawing text.
            # We create a simple SVG wrapper that renders the text in a monospace font.
            svg_content = _ascii_art_to_svg(art_content, style)
            png_bytes = await asyncio.to_thread(_svg_to_png_bytes, svg_content, 3600)

            # Upload to Drive
            file_metadata = {
                "name": f"tufte_diagram_{art_hash[:12]}.png",
                "mimeType": "image/png",
            }
            def _upload_image():
                buf = io.BytesIO(png_bytes)
                media = MediaIoBaseUpload(buf, mimetype="image/png", resumable=True)
                return drive_svc.files().create(
                    body=file_metadata, media_body=media, fields="id"
                ).execute()

            created_file = await asyncio.to_thread(
                _retry_api, _upload_image, "Phase 6 upload image",
            )
            file_id = created_file["id"]

            # Set public permission
            await asyncio.to_thread(
                _retry_api,
                lambda: drive_svc.permissions()
                .create(
                    fileId=file_id,
                    body={"type": "anyone", "role": "reader"},
                )
                .execute(),
                "Phase 6 set permission",
            )

            cache.set_image(art_hash, file_id)
            logger.info(f"[tufte] Phase 6: Uploaded image for '{preceding_heading}': {file_id}")

        # Find the heading in the doc and insert image after it
        doc = await asyncio.to_thread(
            _retry_api,
            lambda: docs_svc.documents().get(documentId=doc_id).execute(),
            "Phase 6 get doc for insert",
        )

        insert_index = _find_heading_end_index(doc, preceding_heading)
        if insert_index is None:
            logger.warning(f"[tufte] Phase 6: Could not find heading '{preceding_heading}' in doc")
            continue

        # Clamp to valid insertion range: Google Docs API rejects
        # insertText at body endIndex (the last valid index is endIndex - 1).
        # This happens when the heading is the last structural element.
        doc_end = _get_doc_length(doc)
        if insert_index >= doc_end:
            insert_index = doc_end - 1

        image_uri = f"https://lh3.googleusercontent.com/d/{file_id}=s0"
        width_pt = min(style.page_width_pt - style.margin_left_pt - style.margin_right_pt - 20, 700)

        # Compute height from aspect ratio of the ASCII art
        art_lines = art_content.split("\n")
        art_max_chars = max((len(line) for line in art_lines), default=1)
        svg_w = int(art_max_chars * 9.6) + 40
        svg_h = len(art_lines) * 18 + 40
        height_pt = int(width_pt * (svg_h / svg_w))

        # Insert newline then image
        insert_requests = [
            {"insertText": {"location": {"index": insert_index}, "text": "\n"}},
        ]
        await asyncio.to_thread(
            _retry_api,
            lambda: docs_svc.documents()
            .batchUpdate(documentId=doc_id, body={"requests": insert_requests})
            .execute(),
            "Phase 6 insert newline",
        )

        # Re-read doc for updated indices
        img_request = [create_insert_image_request(insert_index + 1, image_uri, width_pt, height_pt)]
        await asyncio.to_thread(
            _retry_api,
            lambda: docs_svc.documents()
            .batchUpdate(documentId=doc_id, body={"requests": img_request})
            .execute(),
            "Phase 6 insert image",
        )

        logger.info(f"[tufte] Phase 6: Inserted image after '{preceding_heading}'")


def _ascii_art_to_svg(art: str, style: TufteStyle) -> str:
    """Wrap ASCII/box-drawing art in an SVG that renders it as monospace text."""
    lines = art.split("\n")
    max_width = max((len(line) for line in lines), default=0)
    line_height = 18
    char_width = 9.6  # Approximate for JetBrains Mono at 14px

    svg_width = int(max_width * char_width) + 40
    svg_height = len(lines) * line_height + 40

    # Choose colors based on style
    if style.background is not None:
        # CRT: dark bg, use ink color for strokes
        bg_fill = _rgb_to_hex(style.background)
        text_fill = _rgb_to_hex(style.ink)
    else:
        # Classic: white bg, dark text
        bg_fill = "#FFFFFF"
        text_fill = "#1A1A1A"

    text_elements = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        # Escape XML entities
        escaped = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        y = 20 + (i + 1) * line_height
        text_elements.append(
            f'  <text x="20" y="{y}" '
            f'font-family="JetBrains Mono, Menlo, monospace" '
            f'font-size="14" fill="{text_fill}" '
            f'xml:space="preserve">{escaped}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{svg_width}" height="{svg_height}" '
        f'viewBox="0 0 {svg_width} {svg_height}">\n'
        f'  <rect width="{svg_width}" height="{svg_height}" fill="{bg_fill}" rx="3"/>\n'
        + "\n".join(text_elements)
        + "\n</svg>"
    )


def _rgb_to_hex(color: Dict[str, float]) -> str:
    """Convert an rgbColor dict to a hex string."""
    r = int(color.get("red", 0) * 255)
    g = int(color.get("green", 0) * 255)
    b = int(color.get("blue", 0) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _find_heading_end_index(doc: dict, heading_text: str) -> Optional[int]:
    """Find the endIndex of the paragraph matching *heading_text*."""
    normalized = _normalize(heading_text)
    for elem in doc["body"]["content"]:
        para = elem.get("paragraph")
        if not para:
            continue
        para_text = ""
        for run in para.get("elements", []):
            tr = run.get("textRun")
            if tr:
                para_text += tr.get("content", "")
        if _normalize(para_text.strip()) == normalized:
            return elem["endIndex"]
    return None


# ---------------------------------------------------------------------------
# Phase 7: Pageless mode
# ---------------------------------------------------------------------------


async def _phase7_pageless(docs_svc: Any, doc_id: str) -> None:
    """Set document to pageless mode."""
    logger.info("[tufte] Phase 7: Pageless mode")

    await asyncio.to_thread(
        _retry_api,
        lambda: docs_svc.documents()
        .batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "updateDocumentStyle": {
                            "documentStyle": {
                                "documentFormat": {"documentMode": "PAGELESS"}
                            },
                            "fields": "documentFormat",
                        }
                    }
                ]
            },
        )
        .execute(),
        "Phase 7 pageless",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def publish(
    docs_svc: Any,
    drive_svc: Any,
    markdown_content: str,
    title: str,
    style: TufteStyle,
    cache: TuftePubCache,
    explicit_doc_id: str = "",
) -> Dict[str, Any]:
    """Run the full 9-phase Tufte publishing pipeline.

    Returns dict with doc_id, url, title, style, cached.
    """
    original_md = markdown_content
    was_cached = bool(explicit_doc_id or cache.get_doc_id(title))

    # Preprocess: handle code blocks (ZWJ markers)
    processed_md = _preprocess_code_blocks(markdown_content)

    # Preprocess: fix tables for Google Drive's markdown parser
    processed_md = _preprocess_tables(processed_md)

    # Detect and strip ASCII art blocks
    art_blocks = _detect_ascii_art_blocks(processed_md)
    if art_blocks:
        processed_md = _strip_ascii_art_zones(processed_md, art_blocks)

    # Phase 1: Create or update
    doc_id, link = await _phase1_create_or_update(
        drive_svc, docs_svc, processed_md, title, cache, explicit_doc_id
    )

    # Phase 2: Page setup
    await _phase2_page_setup(docs_svc, doc_id, style)

    # Phase 2.5: Post-table spacing
    await _phase2_5_post_table_spacing(docs_svc, doc_id)

    # Phase 3: Heading styles
    await _phase3_heading_styles(docs_svc, doc_id, original_md, style)

    # Phase 4: Font formatting
    await _phase4_font_formatting(docs_svc, doc_id, style)

    # Phase 4 verification
    await _phase4_verify_font(docs_svc, doc_id)

    # Phase 4.5: Code block styling
    await _phase4_5_code_blocks(docs_svc, doc_id, style)

    # Phase 5: Table styling
    await _phase5_table_styling(docs_svc, doc_id, style)

    # Phase 5.5: Inline bold markers in table cells
    await _phase5_5_table_inline_bold(docs_svc, doc_id, style)

    # Phase 6: Images
    await _phase6_images(docs_svc, drive_svc, doc_id, original_md, style, cache)

    # Phase 7: Pageless mode
    await _phase7_pageless(docs_svc, doc_id)

    logger.info(f"[tufte] Publishing complete: {link}")

    return {
        "doc_id": doc_id,
        "url": link,
        "title": title,
        "style": style.name,
        "cached": was_cached,
    }
