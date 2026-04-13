"""
Tufte Publishing MCP Tools

Exposes the Tufte publishing pipeline as MCP tools.
"""

import json
import logging
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
    markdown_content: str,
    title: str,
    style: str = "classic",
    doc_id: str = "",
) -> str:
    """Publish markdown to Google Docs with Tufte formatting.

    Takes raw markdown content and produces a fully formatted Google Doc
    using the Tufte design system. The 9-phase pipeline handles page setup,
    heading styles, font formatting (JetBrains Mono), code blocks, table
    styling, ASCII art to SVG image conversion, and pageless mode.

    Caches document IDs (title -> doc_id) so re-publishing the same title
    updates the existing doc in place. Also caches uploaded images by
    content hash to avoid re-uploading identical diagrams.

    Args:
        user_google_email: User's Google email address
        markdown_content: Raw markdown text to publish
        title: Document title (used for caching and as the doc name)
        style: Style variant — "classic" (white bg, dark text),
               "crt" or "crt-c" (dark bg, cyan text),
               "crt-a" (dark bg, amber text),
               "crt-g" (dark bg, green text)
        doc_id: Optional existing document ID to update in place
                (overrides the title-based cache lookup)

    Returns:
        JSON string with doc_id, url, title, style, and cached fields
    """
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
