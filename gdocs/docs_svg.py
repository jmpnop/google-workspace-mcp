"""
Google Docs SVG Insertion Tool

Provides an MCP tool to insert SVG illustrations into Google Docs.
Pipeline: SVG content → PNG conversion → Drive upload → public permission → insertInlineImage.
"""

import asyncio
import io
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from googleapiclient.http import MediaIoBaseUpload

from auth.service_decorator import require_multiple_services
from core.server import server
from core.utils import handle_http_errors
from gdocs.docs_helpers import create_insert_image_request

logger = logging.getLogger(__name__)


def _svg_to_png_bytes(svg_content: str, width: int = 1200) -> bytes:
    """Convert SVG string to PNG bytes using rsvg-convert or cairosvg."""
    # Try rsvg-convert first (commonly available via librsvg)
    try:
        result = subprocess.run(
            ["rsvg-convert", "--width", str(width), "--format", "png"],
            input=svg_content.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )
        if result.returncode == 0 and len(result.stdout) > 0:
            logger.info(
                f"[svg_to_png] Converted via rsvg-convert ({len(result.stdout)} bytes)"
            )
            return result.stdout
    except FileNotFoundError:
        logger.debug("[svg_to_png] rsvg-convert not found, trying cairosvg")
    except subprocess.TimeoutExpired:
        logger.warning("[svg_to_png] rsvg-convert timed out")

    # Fallback to cairosvg Python library
    try:
        import cairosvg

        png_bytes = cairosvg.svg2png(
            bytestring=svg_content.encode("utf-8"),
            output_width=width,
        )
        logger.info(f"[svg_to_png] Converted via cairosvg ({len(png_bytes)} bytes)")
        return png_bytes
    except ImportError:
        pass

    raise RuntimeError(
        "No SVG converter available. Install librsvg (brew install librsvg) "
        "or cairosvg (pip install cairosvg)."
    )


@server.tool()
@handle_http_errors("insert_doc_svg", service_type="docs")
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
async def insert_doc_svg(
    docs_service: Any,
    drive_service: Any,
    user_google_email: str,
    document_id: str,
    svg_content: str,
    index: int,
    image_name: str = "illustration",
    width_pts: int = 468,
    height_pts: int = 0,
    caption: str = "",
    render_width_px: int = 1200,
) -> str:
    """
    Insert an SVG illustration into a Google Doc.

    Converts SVG to PNG, uploads to Google Drive, sets public viewing permission,
    and inserts as an inline image at the specified position.

    Args:
        user_google_email: User's Google email address
        document_id: ID of the Google Doc
        svg_content: The SVG markup as a string (full <svg>...</svg> content)
        index: Document position to insert the image (0-based character index)
        image_name: Filename for the uploaded PNG (without extension)
        width_pts: Image width in points in the doc (default 468 = 6.5 inches)
        height_pts: Image height in points (0 = auto-calculate from SVG aspect ratio)
        caption: Optional caption text to insert below the image (italic, centered)
        render_width_px: PNG render width in pixels (default 1200 for crisp display)

    Returns:
        str: Confirmation with Drive file ID and insertion details
    """
    logger.info(
        f"[insert_doc_svg] Doc={document_id}, index={index}, name={image_name}"
    )

    # Ensure index > 0 to avoid section break
    if index <= 0:
        index = 1

    # Step 1: Convert SVG → PNG
    png_bytes = await asyncio.to_thread(_svg_to_png_bytes, svg_content, render_width_px)
    logger.info(f"[insert_doc_svg] PNG size: {len(png_bytes)} bytes")

    # Step 2: Auto-calculate height from SVG viewBox if not specified
    if height_pts <= 0:
        import re

        vb_match = re.search(
            r'viewBox\s*=\s*["\'][\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)["\']',
            svg_content,
        )
        if vb_match:
            svg_w = float(vb_match.group(1))
            svg_h = float(vb_match.group(2))
            height_pts = int(width_pts * (svg_h / svg_w))
            logger.info(
                f"[insert_doc_svg] Auto height from viewBox: {height_pts}pt "
                f"(SVG {svg_w}x{svg_h})"
            )
        else:
            # Fallback: try width/height attributes
            w_match = re.search(r'width\s*=\s*["\'](\d+)', svg_content)
            h_match = re.search(r'height\s*=\s*["\'](\d+)', svg_content)
            if w_match and h_match:
                svg_w = float(w_match.group(1))
                svg_h = float(h_match.group(1))
                height_pts = int(width_pts * (svg_h / svg_w))
            else:
                height_pts = int(width_pts * 0.667)  # Default 3:2 aspect

    # Step 3: Upload PNG to Google Drive
    file_metadata = {
        "name": f"{image_name}.png",
        "mimeType": "image/png",
    }

    media = MediaIoBaseUpload(
        io.BytesIO(png_bytes),
        mimetype="image/png",
        resumable=False,
    )

    created_file = await asyncio.to_thread(
        drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        )
        .execute
    )
    file_id = created_file["id"]
    logger.info(f"[insert_doc_svg] Uploaded to Drive: {file_id}")

    # Step 4: Set public read permission (required for insertInlineImage)
    await asyncio.to_thread(
        drive_service.permissions()
        .create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        )
        .execute
    )
    logger.info(f"[insert_doc_svg] Set public permission on {file_id}")

    # Step 5: Build the image URL
    image_uri = f"https://drive.google.com/uc?export=view&id={file_id}"

    # Step 6: Insert image into the document
    requests = [create_insert_image_request(index, image_uri, width_pts, height_pts)]

    await asyncio.to_thread(
        docs_service.documents()
        .batchUpdate(documentId=document_id, body={"requests": requests})
        .execute
    )
    logger.info(f"[insert_doc_svg] Inserted image at index {index}")

    # Step 7: Add caption if provided
    caption_info = ""
    if caption:
        # Re-read doc to get updated indices
        doc = await asyncio.to_thread(
            docs_service.documents().get(documentId=document_id).execute
        )

        # Find the inline image we just inserted to get its end index
        # The image takes up 1 index position. Caption goes after the newline.
        caption_index = index + 1  # After the inline object

        caption_requests = [
            {
                "insertText": {
                    "location": {"index": caption_index},
                    "text": f"\n{caption}\n",
                }
            },
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": caption_index + 1,
                        "endIndex": caption_index + 1 + len(caption),
                    },
                    "textStyle": {
                        "italic": True,
                        "fontSize": {"magnitude": 9, "unit": "PT"},
                        "foregroundColor": {
                            "color": {
                                "rgbColor": {
                                    "red": 85 / 255,
                                    "green": 85 / 255,
                                    "blue": 85 / 255,
                                }
                            }
                        },
                        "weightedFontFamily": {"fontFamily": "JetBrains Mono"},
                    },
                    "fields": "italic,fontSize,foregroundColor,weightedFontFamily",
                }
            },
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": caption_index + 1,
                        "endIndex": caption_index + 1 + len(caption) + 1,
                    },
                    "paragraphStyle": {"alignment": "CENTER"},
                    "fields": "alignment",
                }
            },
        ]

        await asyncio.to_thread(
            docs_service.documents()
            .batchUpdate(
                documentId=document_id, body={"requests": caption_requests}
            )
            .execute
        )
        caption_info = f", caption: '{caption}'"
        logger.info(f"[insert_doc_svg] Added caption at index {caption_index}")

    link = f"https://docs.google.com/document/d/{document_id}/edit"
    return (
        f"Inserted SVG '{image_name}' as PNG ({width_pts}x{height_pts}pt) "
        f"at index {index}{caption_info}. "
        f"Drive file ID: {file_id}. "
        f"Doc: {link}"
    )
