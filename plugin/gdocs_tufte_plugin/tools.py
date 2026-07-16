"""
Tufte Publishing MCP Tools

Exposes the Tufte publishing pipeline as MCP tools.
"""

import json
import logging
from pathlib import Path
from typing import Any

from auth.service_decorator import require_multiple_services
from core.server import server
from core.utils import handle_http_errors
from gdocs_tufte_plugin.render import crt_raster
from gdocs_tufte_plugin.tufte_cache import TuftePubCache
from gdocs_tufte_plugin.tufte_publisher import publish
from gdocs_tufte_plugin.tufte_styles import get_style

logger = logging.getLogger(__name__)

# Module-level cache instance (shared across calls)
_cache = TuftePubCache()

# CRT style -> raster phosphor palette
_STYLE_PALETTE = {
    "crt": "cyan", "crt-c": "cyan", "crt-a": "amber", "crt-g": "green",
    "cyan": "cyan", "amber": "amber", "green": "green",
}


@server.tool()
@handle_http_errors("publish_markdown_tufte", service_type="docs")
@require_multiple_services(
    [
        {"service_type": "docs", "scopes": "docs_write", "param_name": "docs_service"},
        {
            "service_type": "drive",
            "scopes": "drive_write",
            "param_name": "drive_service",
        },
    ]
)
async def publish_markdown_tufte(
    docs_service: Any,
    drive_service: Any,
    user_google_email: str,
    markdown_content: str = "",
    markdown_file: str = "",
    title: str = "",
    style: str = "classic",
    doc_id: str = "",
) -> str:
    """Publish markdown to Google Docs with Tufte formatting.

    Takes raw markdown content (or a file path) and produces a fully
    formatted Google Doc using the Tufte design system. The 9-phase
    pipeline handles page setup, heading styles, font formatting
    (JetBrains Mono), code blocks, table styling, ASCII art to SVG
    image conversion, and pageless mode.

    Caches document IDs (title -> doc_id) so re-publishing the same title
    updates the existing doc in place. Also caches uploaded images by
    content hash to avoid re-uploading identical diagrams.

    Args:
        user_google_email: User's Google email address
        markdown_content: Raw markdown text to publish (use this OR markdown_file)
        markdown_file: Absolute path to a .md file to read and publish
                       (use this OR markdown_content — avoids token limits
                       when the caller can't pass large content inline)
        title: Document title (used for caching and as the doc name).
               If omitted and markdown_file is set, derived from the filename.
        style: Style variant — "classic" (white bg, dark text),
               "crt" or "crt-c" (dark bg, cyan text),
               "crt-a" (dark bg, amber text),
               "crt-g" (dark bg, green text)
        doc_id: Optional existing document ID to update in place
                (overrides the title-based cache lookup)

    Returns:
        JSON string with doc_id, url, title, style, and cached fields
    """
    base_dir = ""
    if markdown_file and not markdown_content:
        path = Path(markdown_file).expanduser()
        if not path.is_file():
            return json.dumps({"error": f"File not found: {path}"})
        markdown_content = path.read_text(encoding="utf-8")
        base_dir = str(path.parent)
        if not title:
            title = path.stem.replace("_", " ").replace("-", " ").title()

    if not markdown_content:
        return json.dumps({"error": "Provide either markdown_content or markdown_file"})

    if not title:
        return json.dumps({"error": "title is required when using markdown_content"})

    logger.info(
        f"[publish_markdown_tufte] title='{title}', style='{style}', "
        f"doc_id='{doc_id}', content_len={len(markdown_content)}"
    )

    tufte_style = get_style(style)

    result = await publish(
        docs_svc=docs_service,
        drive_svc=drive_service,
        markdown_content=markdown_content,
        title=title,
        style=tufte_style,
        cache=_cache,
        explicit_doc_id=doc_id,
        base_dir=base_dir,
    )

    return json.dumps(result, indent=2)


def _upload_png_to_drive(drive_service: Any, path: str, name: str) -> dict:
    """Upload a PNG to Drive, make it link-readable, return ids/links."""
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(path, mimetype="image/png", resumable=False)
    f = (
        drive_service.files()
        .create(body={"name": name, "mimeType": "image/png"}, media_body=media, fields="id")
        .execute()
    )
    fid = f["id"]
    drive_service.permissions().create(
        fileId=fid, body={"type": "anyone", "role": "reader"}
    ).execute()
    return {
        "file_id": fid,
        "view_link": f"https://drive.google.com/file/d/{fid}/view",
        "image_url": f"https://drive.google.com/uc?id={fid}",
    }


@server.tool()
@handle_http_errors("render_tufte_graphic", service_type="drive")
@require_multiple_services(
    [
        {"service_type": "drive", "scopes": "drive_write", "param_name": "drive_service"},
    ]
)
async def render_tufte_graphic(
    drive_service: Any,
    user_google_email: str,
    kind: str,
    data: dict,
    style: str = "crt",
    title: str = "",
    subtitle: str = "",
    upload: bool = True,
) -> str:
    """Render a Tufte-CRT graphic (table, bar chart, flow diagram, or distribution)
    to a PNG with true CRT effects (phosphor palette, scanlines, glow), and
    optionally upload it to Drive as a link-readable image.

    This is the standalone renderer behind the CRT documents — usable without
    publishing a whole doc (e.g. a Telegram bot embedding a status board).

    Args:
        kind: "table" | "bar" | "diagram" | "distribution".
        data: kind-specific payload:
            table        -> {"headers": [...], "rows": [[...], ...]}
            bar          -> {"labels": [...], "values": [...]}
            diagram      -> {"labels": [...]}   (auto-laid-out flow of boxes)
            distribution -> {"percentiles": {"p10": .., "p50": .., ...}}
        style: "crt"/"crt-c" (cyan), "crt-a" (amber), "crt-g" (green).
        title/subtitle: optional headings.
        upload: if True, upload to Drive and return links; else return local path.

    Returns:
        JSON with the PNG path and (when uploaded) Drive file_id + image_url.
    """
    palette = _STYLE_PALETTE.get(style, "cyan")
    try:
        if kind == "table":
            png = crt_raster.crt_table_png(
                data["headers"], data["rows"], palette=palette,
                title=title or None, subtitle=subtitle or None, name="tufte_table",
            )
        elif kind == "bar":
            png = crt_raster.crt_bar_png(
                data["labels"], data["values"], palette=palette,
                title=title or None, name="tufte_bar",
            )
        elif kind == "diagram":
            png = crt_raster.crt_diagram_png(
                data["labels"], title=title or None, palette=palette, name="tufte_diagram",
            )
        elif kind == "distribution":
            png = crt_raster.crt_distribution_png(
                data["percentiles"], title=title or "DISTRIBUTION",
                subtitle=subtitle, palette=palette, name="tufte_dist",
            )
        else:
            return json.dumps({"error": f"unknown kind '{kind}'"})
    except KeyError as exc:
        return json.dumps({"error": f"missing field for kind '{kind}': {exc}"})

    out = {"kind": kind, "style": style, "palette": palette, "path": png}
    if upload:
        out.update(_upload_png_to_drive(drive_service, png, title or f"tufte_{kind}"))
    return json.dumps(out, indent=2)
