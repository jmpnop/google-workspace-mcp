"""
Vector ASCII / box-drawing renderer for the Tufte publisher.

Renders a block of monospace box-drawing / ASCII art to an SVG whose glyphs are
the vendored JetBrains Mono **outlines**, placed on an explicit character grid.
Every glyph is emitted as a vector ``<path>`` (not ``<text>``), so the output is
fully deterministic and **independent of the SVG rasterizer's font resolution**:
no ``@font-face``, no fontconfig, no system-font substitution, no per-glyph
fallback. This eliminates the column-drift / sheared-box artifacts that appear
when a rasterizer places characters by natural glyph advance and silently falls
back to a font whose box-drawing / arrow glyphs advance differently than assumed.

Two root causes are addressed together:

1. **No fixed grid.** Character *N* is pinned to ``x = PAD + N * CHAR_W`` rather
   than wherever the cumulative advance of characters ``0..N-1`` happens to land,
   so a single mis-advancing glyph can never shift its neighbours or shear the
   rows below it.
2. **Unguaranteed font.** librsvg (the default rasterizer, ``rsvg-convert``)
   ignores CSS ``@font-face`` and resolves families through fontconfig — so a
   name-only ``font-family`` is at the mercy of whatever the host has installed.
   Embedding the actual glyph outlines removes font resolution from the pipeline
   entirely: the same SVG rasterizes identically on macOS, Linux, cairosvg,
   resvg and Chrome.

Grid model (SVG user units == px)::

    x(col)        = PAD + col * CHAR_W          # cell left edge
    baseline(row) = PAD + (row + 1) * LINE_H
    CHAR_W        = FONT_SIZE * advance / unitsPerEm   # measured from the font

The vendored JetBrains Mono is a uniform monospace (advance 600/1000 em, so
``CHAR_W`` = 8.4px at 14px — not the historical guess of 9.6) and covers the full
light/heavy/double box-drawing set plus the geometric arrows (▼ ► ▲ ◄) and the
Unicode arrows (→ ← ↓ ↑); ``verify_glyph_coverage`` checks this against the font.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layout constants (SVG user units). Kept identical to the historical
# text-based renderer so published-document geometry is unchanged, EXCEPT that
# the horizontal cell pitch is now the *measured* advance instead of a guess.
# ---------------------------------------------------------------------------
FONT_SIZE = 14
LINE_H = 18
PAD = 20
TAB_WIDTH = 8  # Expand tabs before gridding so a tab can't collapse a column.

# JetBrains Mono's advance is 600/1000 em, i.e. 8.4px at FONT_SIZE. Used as the
# cell pitch when the font can't be measured, so dimension math (and the text
# fallback's geometry) stay consistent with the vector grid instead of raising.
_NOMINAL_CHAR_W = FONT_SIZE * 0.6

# Bumped whenever the rendered output changes, so the publisher's image cache
# (keyed on the art content) regenerates diagrams instead of reusing a PNG made
# by an older renderer. "1" was the legacy text-based <text> SVG; "2" is the
# deterministic vector-glyph grid.
RENDER_VERSION = "2"

# Same vendoring convention as render/crt_raster.py (TUFTE_FONT_DIR override).
_FONT_DIR = Path(
    os.getenv("TUFTE_FONT_DIR", str(Path(__file__).resolve().parent.parent / "fonts"))
)
_FONT_PATH = _FONT_DIR / "JetBrainsMonoNerdFont-Regular.ttf"

# The full box-drawing / arrow repertoire the publisher may emit. Mirrors
# tufte_publisher._BOX_CHARS; verify_glyph_coverage() asserts the font has them.
_REQUIRED_GLYPHS = "┌┐└┘─│├┤┬┴┼═║╔╗╚╝╠╣╦╩╬▼►▲◄→←↓↑"


# ---------------------------------------------------------------------------
# Font access (loaded once, lazily)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _font():
    """Load the vendored font once and return (glyphset, cmap, upm, advance).

    Raises if fontTools or the vendored font is unavailable; callers that want
    resilience (the publisher) catch this and fall back to text rendering.
    """
    from fontTools.ttLib import TTFont

    font = TTFont(str(_FONT_PATH))
    upm = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    glyphset = font.getGlyphSet()
    hmtx = font["hmtx"]
    # Reference advance: 'M' is always present; in a monospace every glyph shares
    # this advance, which is exactly why the grid pitch can be a single constant.
    ref_gid = cmap.get(ord("M")) or next(iter(cmap.values()))
    advance = hmtx[ref_gid][0]
    return glyphset, cmap, upm, advance


def char_width() -> float:
    """Horizontal cell pitch in px for FONT_SIZE (JetBrains Mono: 8.4).

    Measured from the vendored font; falls back to the known nominal advance if
    the font can't be loaded, so callers that only need geometry
    (``ascii_svg_dimensions``, the text fallback) never raise on a broken font
    environment — that is what keeps a diagram from hard-failing a publish.
    """
    try:
        _, _, upm, advance = _font()
        return FONT_SIZE * advance / upm
    except Exception:
        return _NOMINAL_CHAR_W


@lru_cache(maxsize=8192)
def _glyph_path(ch: str) -> Optional[str]:
    """SVG path ``d`` for *ch*: scaled to FONT_SIZE px, y increasing downward,
    origin at the glyph's pen origin (baseline at y=0, left sidebearing at x=0).

    Returns ``None`` when the glyph is absent from the font or has no outline
    (e.g. the space), so the caller can simply skip that cell — its column
    position is implicit in the grid, no advance is consumed from a neighbour.
    """
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen

    glyphset, cmap, upm, _ = _font()
    gid = cmap.get(ord(ch))
    if gid is None:
        return None
    scale = FONT_SIZE / upm
    svg_pen = SVGPathPen(glyphset)
    # Flip Y (font units are y-up; SVG is y-down) and scale to px in one matrix.
    glyphset[gid].draw(TransformPen(svg_pen, (scale, 0, 0, -scale, 0, 0)))
    return svg_pen.getCommands() or None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_glyph_coverage(chars: str = _REQUIRED_GLYPHS) -> List[str]:
    """Return the characters in *chars* that the vendored font cannot render."""
    _, cmap, _, _ = _font()
    return [c for c in chars if ord(c) not in cmap]


def ascii_svg_dimensions(art: str) -> Tuple[int, int]:
    """Canvas (width, height) in px for *art* on the character grid.

    Single source of truth for the diagram's aspect ratio: the publisher uses
    this to size the inline image so the doc placement matches the PNG exactly.
    """
    lines = art.expandtabs(TAB_WIDTH).split("\n")
    n_cols = max((len(line) for line in lines), default=0)
    width = int(round(n_cols * char_width())) + 2 * PAD
    height = len(lines) * LINE_H + 2 * PAD
    return width, height


def ascii_art_to_svg(art: str, ink_hex: str, bg_hex: str) -> str:
    """Render *art* to a self-contained SVG of vector glyph paths on the grid.

    ``ink_hex`` / ``bg_hex`` are ``#RRGGBB`` strings (glyph fill / background).
    Falls back to a text-based SVG only if the font/outline machinery is
    unavailable, so a diagram can never hard-fail a publish.
    """
    art = art.expandtabs(TAB_WIDTH)
    try:
        return _vector_svg(art, ink_hex, bg_hex)
    except Exception as exc:  # pragma: no cover - defensive: keep publish alive
        logger.error(
            "[ascii_svg] vector render failed (%s); falling back to text SVG. "
            "Box-art alignment is not guaranteed in this mode.",
            exc,
        )
        return _text_fallback_svg(art, ink_hex, bg_hex)


def _vector_svg(art: str, ink_hex: str, bg_hex: str) -> str:
    lines = art.split("\n")
    cw = char_width()
    width, height = ascii_svg_dimensions(art)

    missing = set()
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{bg_hex}" rx="3"/>',
    ]
    for row, line in enumerate(lines):
        baseline = PAD + (row + 1) * LINE_H
        for col, ch in enumerate(line):
            if ch == " ":
                continue
            d = _glyph_path(ch)
            if not d:
                if ch in _REQUIRED_GLYPHS:
                    missing.add(ch)
                continue
            x0 = PAD + col * cw
            # Path 'd' is baseline-relative px; a translate is all each cell needs.
            parts.append(
                f'<path transform="translate({x0:.3f},{baseline})" '
                f'd="{d}" fill="{ink_hex}"/>'
            )
    parts.append("</svg>")

    if missing:
        logger.warning(
            "[ascii_svg] vendored font is missing box-drawing glyph(s) %s; "
            "they were dropped from the diagram.",
            "".join(sorted(missing)),
        )
    return "\n".join(parts)


def _text_fallback_svg(art: str, ink_hex: str, bg_hex: str) -> str:
    """Legacy text-based SVG (one <text> per line). Used only if the vector path
    is unavailable; alignment then depends on the rasterizer's font."""
    lines = art.split("\n")
    # Use the same cell pitch as ascii_svg_dimensions so the publisher's
    # aspect-ratio math matches this SVG's geometry even on the fallback path.
    width, height = ascii_svg_dimensions(art)

    texts = []
    for row, line in enumerate(lines):
        if not line.strip():
            continue
        escaped = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        y = PAD + (row + 1) * LINE_H
        texts.append(
            f'<text x="{PAD}" y="{y}" '
            f'font-family="JetBrains Mono, Menlo, monospace" '
            f'font-size="{FONT_SIZE}" fill="{ink_hex}" '
            f'xml:space="preserve">{escaped}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'  <rect width="{width}" height="{height}" fill="{bg_hex}" rx="3"/>\n'
        + "\n".join(texts)
        + "\n</svg>"
    )
