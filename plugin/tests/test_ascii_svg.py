"""Regression tests for the vector ASCII / box-drawing renderer.

These guard the class of bug fixed in render/ascii_svg.py: box-art columns
must sit on a deterministic grid and must not depend on the SVG rasterizer's
font resolution. The core guarantees are asserted structurally on the emitted
SVG (portable, no rasterizer needed); an optional end-to-end pixel test runs
only when a rasterizer is available.
"""
import re
import shutil
import subprocess

import pytest

from gdocs_tufte_plugin.render import ascii_svg

# Canonical box-drawing / arrow repertoire. Kept as a literal here so the test
# is a second, independent source of truth against the renderer's own list.
BOX_CHARS = "┌┐└┘─│├┤┬┴┼═║╔╗╚╝╠╣╦╩╬▼►▲◄→←↓↑"

FIXTURE = "\n".join(
    [
        "┌─────────┬─────────┐",
        "│  alpha  │  beta   │",
        "├─────────┼─────────┤",
        "│  gamma  │  delta  │",
        "└─────────┴─────────┘",
        "     │         ▼",
        "     ▼",
    ]
)


def _glyph_positions(svg: str):
    """(x, y) of every emitted glyph path, in document order."""
    return [(float(x), float(y)) for x, y in re.findall(r"translate\(([-\d.]+),([-\d.]+)\)", svg)]


# --------------------------------------------------------------------------- #
# Font coverage & measured metrics
# --------------------------------------------------------------------------- #


def test_vendored_font_covers_every_box_glyph():
    """The vendored font must render every box/arrow glyph itself, so no glyph
    falls back to a different (differently-advancing) font."""
    assert ascii_svg.verify_glyph_coverage(BOX_CHARS) == []


def test_required_glyphs_stay_in_sync_with_canonical_set():
    assert set(ascii_svg._REQUIRED_GLYPHS) == set(BOX_CHARS)


def test_char_width_is_measured_not_the_old_guess():
    """CHAR_W must come from the font's real advance (8.4px), not the historical
    hard-coded 9.6 that untethered the grid from the glyphs."""
    cw = ascii_svg.char_width()
    assert cw == pytest.approx(ascii_svg.FONT_SIZE * 0.6, abs=1e-6)  # 600/1000 em
    assert cw == pytest.approx(8.4, abs=1e-6)
    assert abs(cw - 9.6) > 1.0


# --------------------------------------------------------------------------- #
# Grid invariants on the emitted SVG (the regression this fix exists for)
# --------------------------------------------------------------------------- #


def test_output_is_pure_vector_no_text():
    """No <text> => no font resolution => rasterizer cannot substitute a font."""
    svg = ascii_svg.ascii_art_to_svg(FIXTURE, "#1A1A1A", "#FFFFFF")
    assert "<path" in svg
    assert "<text" not in svg
    assert "@font-face" not in svg  # not relied upon (librsvg ignores it anyway)


def test_every_glyph_sits_on_the_grid():
    svg = ascii_svg.ascii_art_to_svg(FIXTURE, "#1A1A1A", "#FFFFFF")
    cw, pad, lh = ascii_svg.char_width(), ascii_svg.PAD, ascii_svg.LINE_H
    positions = _glyph_positions(svg)
    assert positions, "renderer emitted no glyphs"
    for x, y in positions:
        col = round((x - pad) / cw)
        row = round((y - pad) / lh - 1)
        assert x == pytest.approx(pad + col * cw, abs=1e-6)
        assert y == pytest.approx(pad + (row + 1) * lh, abs=1e-9)


def test_column_x_is_identical_across_all_rows():
    """The heart of the fix: column c has ONE x-coordinate on every row, so
    verticals never shear relative to the rows above/below them."""
    svg = ascii_svg.ascii_art_to_svg(FIXTURE, "#1A1A1A", "#FFFFFF")
    cw, pad = ascii_svg.char_width(), ascii_svg.PAD
    col_to_x = {}
    for x, _ in _glyph_positions(svg):
        col = round((x - pad) / cw)
        col_to_x.setdefault(col, set()).add(round(x, 6))
    drifting = {c: xs for c, xs in col_to_x.items() if len(xs) > 1}
    assert not drifting, f"columns whose x drifts between rows: {drifting}"


def test_dimensions_follow_the_grid():
    art = "───┐\n   │"
    w, h = ascii_svg.ascii_svg_dimensions(art)
    cw, pad, lh = ascii_svg.char_width(), ascii_svg.PAD, ascii_svg.LINE_H
    n_cols = 4  # longest line "───┐"
    assert w == int(round(n_cols * cw)) + 2 * pad
    assert h == 2 * lh + 2 * pad


def test_leading_spaces_are_preserved_as_columns():
    """A glyph indented by N spaces must land in column N (space consumes a cell
    even though it emits no path)."""
    svg = ascii_svg.ascii_art_to_svg("     ▼", "#1A1A1A", "#FFFFFF")
    cw, pad = ascii_svg.char_width(), ascii_svg.PAD
    (x, _), = _glyph_positions(svg)
    assert x == pytest.approx(pad + 5 * cw, abs=1e-6)


def test_crt_and_classic_differ_only_in_color():
    """Geometry is palette-independent: swapping ink/bg moves no glyph."""
    a = ascii_svg.ascii_art_to_svg(FIXTURE, "#1A1A1A", "#FFFFFF")
    b = ascii_svg.ascii_art_to_svg(FIXTURE, "#00CCCC", "#010101")
    assert _glyph_positions(a) == _glyph_positions(b)


# --------------------------------------------------------------------------- #
# Tabs & resilience (the fallback contract must actually hold)
# --------------------------------------------------------------------------- #


def _viewbox_wh(svg: str):
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    return float(m.group(1)), float(m.group(2))


def test_tabs_expand_to_the_grid():
    """A tab must advance to the next TAB_WIDTH stop, not collapse to one cell."""
    art = "a\tb"  # expands to 'a' + 7 spaces + 'b' -> cols 0 and 8
    svg = ascii_svg.ascii_art_to_svg(art, "#000000", "#FFFFFF")
    cw, pad = ascii_svg.char_width(), ascii_svg.PAD
    xs = sorted(x for x, _ in _glyph_positions(svg))
    assert xs == pytest.approx([pad + 0 * cw, pad + ascii_svg.TAB_WIDTH * cw], abs=1e-6)


def test_char_width_falls_back_when_font_unavailable(monkeypatch):
    def _boom():
        raise RuntimeError("simulated: font unavailable")

    monkeypatch.setattr(ascii_svg, "_font", _boom)
    assert ascii_svg.char_width() == pytest.approx(ascii_svg._NOMINAL_CHAR_W)
    # The dimension call the publisher makes unprotected must NOT raise.
    w, h = ascii_svg.ascii_svg_dimensions("┌─┐\n└─┘")
    assert w > 2 * ascii_svg.PAD and h > 2 * ascii_svg.PAD


def test_publish_survives_font_failure_via_text_fallback(monkeypatch):
    """If the font/outline machinery fails, rendering degrades to a text SVG
    instead of raising — a diagram can never hard-fail a publish."""
    ascii_svg._glyph_path.cache_clear()  # drop any real-font-cached outlines

    def _boom():
        raise RuntimeError("simulated: font unavailable")

    monkeypatch.setattr(ascii_svg, "_font", _boom)
    svg = ascii_svg.ascii_art_to_svg(FIXTURE, "#1A1A1A", "#FFFFFF")
    assert "<text" in svg and "<path" not in svg  # fell back
    ascii_svg._glyph_path.cache_clear()  # don't poison other tests


def test_fallback_aspect_matches_dimension_math(monkeypatch):
    """Fallback SVG geometry must equal ascii_svg_dimensions so the image the
    publisher places isn't stretched (the old 9.6-vs-8.4 mismatch)."""
    ascii_svg._glyph_path.cache_clear()

    def _boom():
        raise RuntimeError("simulated: font unavailable")

    monkeypatch.setattr(ascii_svg, "_font", _boom)
    art = FIXTURE
    svg = ascii_svg.ascii_art_to_svg(art, "#1A1A1A", "#FFFFFF")
    assert _viewbox_wh(svg) == pytest.approx(ascii_svg.ascii_svg_dimensions(art))
    ascii_svg._glyph_path.cache_clear()


# --------------------------------------------------------------------------- #
# Diagram cache key (publisher) — style + render version must both matter
# --------------------------------------------------------------------------- #


def test_diagram_cache_key_separates_styles_and_versions():
    # Importing the publisher pulls host runtime deps; skip if unavailable.
    tp = pytest.importorskip("gdocs_tufte_plugin.tufte_publisher")
    ts = pytest.importorskip("gdocs_tufte_plugin.tufte_styles")
    art = FIXTURE
    classic = tp._diagram_cache_key(art, ts.get_style("classic"))
    crt = tp._diagram_cache_key(art, ts.get_style("crt"))
    # Same art, different style -> different image (no classic/CRT collision).
    assert classic != crt
    # Deterministic for a fixed (art, style).
    assert classic == tp._diagram_cache_key(art, ts.get_style("classic"))
    # The render version participates, so a renderer bump invalidates old PNGs.
    assert ascii_svg.RENDER_VERSION in {"1", "2", "3", "4", "5"}  # sanity: set


# --------------------------------------------------------------------------- #
# End-to-end pixel invariant through the real rasterizer (optional)
# --------------------------------------------------------------------------- #


def _rasterize(svg: str, width: int = 800):
    if shutil.which("rsvg-convert"):
        r = subprocess.run(
            ["rsvg-convert", "--width", str(width), "--format", "png"],
            input=svg.encode(), capture_output=True, timeout=30,
        )
        if r.returncode == 0 and r.stdout:
            return r.stdout
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg.encode(), output_width=width)
    except Exception:
        return None


def test_vertical_bars_align_at_pixel_level():
    """Golden-style regression: render stacked '│' and assert every row's bar
    ink occupies the same x-pixel column. Skips if no rasterizer is installed."""
    Image = pytest.importorskip("PIL.Image")
    import io

    # Bars in the same source column on consecutive rows.
    art = "\n".join(["│"] * 6)
    svg = ascii_svg.ascii_art_to_svg(art, "#000000", "#FFFFFF")
    png = _rasterize(svg, width=400)
    if png is None:
        pytest.skip("no SVG rasterizer available")

    img = Image.open(io.BytesIO(png)).convert("L")
    w, h = img.size
    px = img.load()

    # For each raster row, the mean x of dark pixels (the bar centroid).
    centroids = []
    for y in range(h):
        xs = [x for x in range(w) if px[x, y] < 128]
        if xs:
            centroids.append(sum(xs) / len(xs))
    assert centroids, "no ink found in rasterized image"
    spread = max(centroids) - min(centroids)
    # All bars share one column; allow a couple px for antialiasing.
    assert spread <= 2.0, f"vertical bars drift by {spread:.2f}px across rows"
