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
from gdocs.tufte_cache import TuftePubCache
from gdocs.tufte_publisher import publish
from gdocs.tufte_styles import get_style

logger = logging.getLogger(__name__)

# Module-level cache instance (shared across calls)
_cache = TuftePubCache()


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
    if markdown_file and not markdown_content:
        path = Path(markdown_file).expanduser()
        if not path.is_file():
            return json.dumps({"error": f"File not found: {path}"})
        markdown_content = path.read_text(encoding="utf-8")
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
    )

    return json.dumps(result, indent=2)
