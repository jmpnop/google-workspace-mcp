#!/usr/bin/env python3
"""Tufte-styled CRT renderer.

Reusable library for generating monochrome terminal-style tables, bar charts,
and flow diagrams as PNG images with Tufte design principles (heavy framing
rules, brightness hierarchy, minimal structural ink) and CRT effects
(scanlines, glow, vignette).

Usage:
    uv run --with Pillow agents/crt_render.py               # run built-in demo
    from crt_render import crt_table_png, crt_bar_png        # import as library
"""

import math
import os
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Fonts are vendored inside the plugin package (../fonts) — no machine-specific
# absolute paths. Override with TUFTE_FONT_DIR if a different install is wanted.
_FONT_DIR = Path(os.getenv("TUFTE_FONT_DIR", str(Path(__file__).resolve().parent.parent / "fonts")))
FONT_REGULAR = str(_FONT_DIR / "JetBrainsMonoNerdFont-Regular.ttf")
FONT_BOLD = str(_FONT_DIR / "JetBrainsMonoNerdFont-Bold.ttf")

PALETTES = {
    "green": {
        "bright": (0, 255, 65),
        "normal": (0, 204, 52),
        "dim": (0, 140, 36),
        "faint": (0, 80, 20),
        "ghost": (0, 45, 12),
    },
    "amber": {
        "bright": (255, 176, 0),
        "normal": (204, 141, 0),
        "dim": (153, 106, 0),
        "faint": (90, 62, 0),
        "ghost": (50, 35, 0),
    },
    "cyan": {
        "bright": (0, 255, 255),
        "normal": (0, 204, 204),
        "dim": (0, 140, 140),
        "faint": (0, 80, 80),
        "ghost": (0, 45, 45),
    },
}

BG = (0, 0, 0)
MARGIN = 192


# ── Core rendering ────────────────────────────────────────────────


def crt_font(size=16, bold=False):
    path = FONT_BOLD if bold else FONT_REGULAR
    return ImageFont.truetype(path, size)


def crt_canvas(w, h):
    return Image.new("RGBA", (w, h), BG + (255,))


def crt_finalize(img, scanline_gap=6, glow_radius=5, vignette=True):
    """Apply CRT effects: glow, scanlines, vignette. Returns RGBA."""
    w, h = img.size

    glow = img.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    result = Image.alpha_composite(glow, img)

    scanlines = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scanlines)
    for y in range(0, h, scanline_gap):
        sd.line([(0, y), (w, y)], fill=(0, 0, 0, 38), width=1)
    result = Image.alpha_composite(result, scanlines)

    if vignette and w > 300:
        vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vig)
        edge = 180
        for i in range(edge):
            alpha = int(70 * (1 - i / edge))
            vd.rectangle([i, i, w - i, h - i], outline=(0, 0, 0, alpha))
        result = Image.alpha_composite(result, vig)

    return result


def crt_save_gif(frames, durations, name="crt_output"):
    """Save frames as animated GIF. Returns file path."""
    rgb_frames = [f.convert("RGB") for f in frames]
    ts = int(time.time())
    path = f"/tmp/crt_{name}_{ts}_{os.getpid()}.gif"
    rgb_frames[0].save(
        path,
        save_all=True,
        append_images=rgb_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    print(path)
    print(f"{len(frames)} frames, ~{sum(durations) / 1000:.1f}s total")
    return path


MAX_IMG_DIM = 5000  # Telegram sendPhoto rejects images wider than ~10000px


def crt_save_png(img, name="crt_output"):
    """Save a single RGBA frame as PNG. Enforces 16:9 max aspect ratio and
    scales down if too large. Returns file path."""
    w, h = img.size
    # Enforce 16:9 max aspect ratio by extending canvas height
    max_aspect = 16 / 9
    if h > 0 and w / h > max_aspect:
        new_h = int(math.ceil(w / max_aspect))
        padded = Image.new("RGBA", (w, new_h), BG + (255,))
        padded.paste(img, (0, 0))
        img = padded
        w, h = w, new_h
    if w > MAX_IMG_DIM or h > MAX_IMG_DIM:
        scale = MAX_IMG_DIM / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        w, h = new_w, new_h
    ts = int(time.time())
    path = f"/tmp/crt_{name}_{ts}_{os.getpid()}.png"
    img.convert("RGB").save(path, "PNG")
    print(f"{path} ({w}x{h})")
    return path


# ── Table ─────────────────────────────────────────────────────────


def _auto_col_widths(headers, rows):
    """Calculate column widths in characters."""
    widths = []
    for ci in range(len(headers)):
        max_len = len(headers[ci])
        for row in rows:
            if ci < len(row):
                max_len = max(max_len, len(str(row[ci])))
        widths.append(max_len + 2)
    return widths


def _wrap_text(text, max_chars):
    """Word-wrap text to fit within max_chars per line."""
    if len(text) <= max_chars:
        return text
    if max_chars < 4:
        max_chars = 4
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if not current:
            # Force-break words longer than max_chars
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines) if lines else text


def _reflow_for_aspect(headers, rows, col_widths, font_size,
                        has_title=False, has_subtitle=False):
    """Constrain table to 16:9 max aspect ratio by reflowing cell text.

    Strategy:
    1. Compute min column widths from longest cell value AND longest
       header word (headers wrap only at word boundaries).
    2. Iteratively narrow columns, wrapping long text cells.
    3. If still too wide after wrapping, reduce font_size.

    Returns (new_rows, new_col_widths, row_line_counts, new_font_size).
    """
    MAX_ASPECT = 16 / 9
    MIN_FONT = max(36, font_size // 2)

    # Min width per column: max(longest_word_in_cells, longest_header_word) + 2
    # Uses longest WORD (not full value) so long text cells can wrap.
    # Numeric cells use full value width (numbers don't wrap).
    min_widths = []
    for ci in range(len(headers)):
        max_word_len = 0
        for row in rows:
            if ci < len(row):
                text = str(row[ci])
                if _is_numeric(text):
                    # Numeric values don't wrap — use full width
                    max_word_len = max(max_word_len, len(text))
                else:
                    # Text values: longest single word
                    for word in text.split():
                        max_word_len = max(max_word_len, len(word))
        max_hdr_word = max((len(w) for w in headers[ci].split()), default=0)
        min_widths.append(max(max_word_len + 2, max_hdr_word + 2, 6))

    def _try_reflow(fs):
        char_w = fs * 10 // 16
        row_h = int(fs * 2.0)

        def _calc_dims(cwidths, rlcounts):
            tw = sum(cw * char_w for cw in cwidths) + char_w * 2
            w = tw + 2 * MARGIN
            # Compute header line count
            hlc = 1
            for ci2, hdr2 in enumerate(headers):
                usable2 = cwidths[ci2] - 2
                if len(hdr2) > usable2:
                    hlc = max(hlc, _wrap_text(hdr2, max(4, usable2)).count("\n") + 1)
            title_h = row_h if has_title else 0
            sub_h = row_h if has_subtitle else 0
            gap_h = int(row_h * 0.3) if (has_title or has_subtitle) else 0
            hdr_block = title_h + sub_h + gap_h + 9 + (row_h * hlc) + 8
            data_h = sum(rlc * row_h for rlc in rlcounts)
            h = hdr_block + data_h + row_h + 2 * MARGIN + row_h
            return w, h

        rlc_cur = [1] * len(rows)
        w, h = _calc_dims(col_widths, rlc_cur)
        if w / h <= MAX_ASPECT:
            return rows, col_widths, rlc_cur, True

        cur_widths = list(col_widths)
        for _pass in range(20):
            w, h = _calc_dims(cur_widths, rlc_cur)
            if w / h <= MAX_ASPECT:
                break
            ratio = (h * MAX_ASPECT) / w if w > 0 else 1.0
            if ratio >= 1.0:
                break
            new_w = [max(min_widths[i], round(cw * ratio))
                     for i, cw in enumerate(cur_widths)]
            if new_w == cur_widths:
                break
            cur_widths = new_w
            # Recompute line counts
            rlc_cur = []
            for row in rows:
                ml = 1
                for ci, cell in enumerate(row):
                    usable = max(4, cur_widths[ci] - 2)
                    ml = max(ml, _wrap_text(str(cell), usable).count("\n") + 1)
                rlc_cur.append(ml)

        # Final wrap
        new_rows = []
        rlc_final = []
        for row in rows:
            new_row = []
            ml = 1
            for ci, cell in enumerate(row):
                text = str(cell)
                usable = max(4, cur_widths[ci] - 2)
                wrapped = _wrap_text(text, usable)
                new_row.append(wrapped)
                ml = max(ml, wrapped.count("\n") + 1)
            new_rows.append(new_row)
            rlc_final.append(ml)

        w, h = _calc_dims(cur_widths, rlc_final)
        fits = (w / h <= MAX_ASPECT)
        return new_rows, cur_widths, rlc_final, fits

    # Try at current font size first
    new_rows, new_widths, rlc, fits = _try_reflow(font_size)
    if fits:
        return new_rows, new_widths, rlc, font_size

    # Reduce font size until it fits
    for fs in range(font_size - 4, MIN_FONT - 1, -4):
        new_rows, new_widths, rlc, fits = _try_reflow(fs)
        if fits:
            return new_rows, new_widths, rlc, fs

    return new_rows, new_widths, rlc, MIN_FONT


def _is_numeric(text):
    """Check if text looks numeric (for right-alignment)."""
    try:
        float(
            text.replace(",", "")
            .replace("$", "")
            .replace("+", "")
            .replace("%", "")
            .replace("\u2212", "-")
        )
        return True
    except ValueError:
        return False


def _render_table_frame(
    headers,
    rows,
    col_widths,
    visible_rows,
    palette="green",
    title=None,
    subtitle=None,
    font_size=72,
    cursor_on=False,
    cursor_row=None,
    cell_colors=None,
    row_line_counts=None,
):
    """Render one frame of a Tufte-styled CRT table.

    Tufte principles adapted for dark background:
    - Heavy top/bottom framing rules (bright)
    - Faint header background fill
    - Light horizontal row separators (no alternating tints)
    - Consistent body text brightness
    - Typography weight hierarchy (bold headers, regular body)

    row_line_counts: optional list of ints, number of text lines per row
    (for multi-line cells from aspect ratio reflow). Default: 1 per row.
    """
    pal = PALETTES[palette]
    font = crt_font(font_size)
    font_bold = crt_font(font_size, bold=True)
    char_w = font_size * 10 // 16
    row_h = int(font_size * 2.0)
    text_pad = int(row_h * 0.12)

    if not row_line_counts:
        row_line_counts = [1] * len(rows)

    # Pre-compute header line count (headers wrap if column is narrow)
    hdr_lc = 1
    for ci, hdr in enumerate(headers):
        usable = col_widths[ci] - 2
        if len(hdr) > usable:
            hdr_lc = max(hdr_lc, _wrap_text(hdr, max(4, usable)).count("\n") + 1)

    table_w = sum(cw * char_w for cw in col_widths) + char_w * 2
    title_h = row_h if title else 0
    sub_h = row_h if subtitle else 0
    gap_h = int(row_h * 0.3) if (title or subtitle) else 0
    # top rule(3+6) + header(hdr_lc * row_h) + header rule(2+6)
    header_block = title_h + sub_h + gap_h + 9 + (row_h * hdr_lc) + 8
    data_h = sum(rlc * row_h for rlc in row_line_counts)
    img_w = table_w + 2 * MARGIN
    img_h = header_block + data_h + row_h + 2 * MARGIN + row_h

    img = crt_canvas(img_w, img_h)
    draw = ImageDraw.Draw(img)
    y = MARGIN

    # Title
    if title:
        draw.text((MARGIN, y), title, font=font_bold, fill=pal["bright"] + (255,))
        y += row_h
    # Subtitle
    if subtitle:
        sub_font = crt_font(font_size - 4)
        draw.text(
            (MARGIN, y), subtitle, font=sub_font, fill=pal["dim"] + (255,)
        )
        y += row_h
    if title or subtitle:
        y += int(row_h * 0.3)

    # ── Heavy top rule (Tufte framing) ──
    draw.line(
        [(MARGIN, y), (img_w - MARGIN, y)],
        fill=pal["bright"] + (220,), width=3,
    )
    y += 6

    # ── Header row with faint background fill ──
    # Headers may wrap if column is narrower than header text
    hdr_line_count = 1
    for ci, hdr in enumerate(headers):
        usable = col_widths[ci] - 2
        if len(hdr) > usable:
            wrapped = _wrap_text(hdr, max(4, usable))
            hdr_line_count = max(hdr_line_count, wrapped.count("\n") + 1)
    hdr_h = hdr_line_count * row_h

    draw.rectangle(
        [MARGIN, y, img_w - MARGIN, y + hdr_h],
        fill=pal["ghost"] + (70,),
    )
    x = MARGIN + char_w
    for ci, hdr in enumerate(headers):
        cw_px = col_widths[ci] * char_w
        usable = col_widths[ci] - 2
        if len(hdr) > usable:
            hdr = _wrap_text(hdr, max(4, usable))
        hdr_lines = hdr.split("\n")
        for li, hl in enumerate(hdr_lines):
            hy = y + text_pad + li * row_h
            if _is_numeric(hl):
                tx = x + cw_px - (len(hl) + 1) * char_w
            else:
                tx = x
            draw.text((tx, hy), hl, font=font_bold, fill=pal["bright"] + (255,))
        x += cw_px
    y += hdr_h

    # ── Medium rule below header ──
    draw.line(
        [(MARGIN, y), (img_w - MARGIN, y)],
        fill=pal["normal"] + (220,), width=2,
    )
    y += 6

    # Track where data rows start (for cursor positioning)
    data_start_y = y

    # ── Data rows with Tufte-style separators ──
    n_visible = min(visible_rows, len(rows))
    for ri in range(n_visible):
        row = rows[ri]
        rlc = row_line_counts[ri]
        row_px_h = rlc * row_h
        x = MARGIN + char_w

        for ci, cell in enumerate(row):
            cw_px = col_widths[ci] * char_w
            text = str(cell)
            lines = text.split("\n")

            if cell_colors and (ri, ci) in cell_colors:
                color = cell_colors[(ri, ci)] + (255,)
            else:
                color = pal["normal"] + (255,)

            for line_idx, line_text in enumerate(lines):
                line_y = y + text_pad + line_idx * row_h
                if _is_numeric(line_text):
                    tx = x + cw_px - (len(line_text) + 1) * char_w
                else:
                    tx = x
                draw.text((tx, line_y), line_text, font=font, fill=color)
            x += cw_px
        y += row_px_h

        # Faint row separator (Tufte: light internal rules)
        if ri < n_visible - 1:
            draw.line(
                [(MARGIN, y), (img_w - MARGIN, y)],
                fill=pal["faint"] + (50,), width=1,
            )

    # ── Heavy bottom rule (Tufte framing) ──
    if visible_rows >= len(rows):
        draw.line(
            [(MARGIN, y + 4), (img_w - MARGIN, y + 4)],
            fill=pal["bright"] + (220,), width=2,
        )

    # Blinking cursor
    if cursor_on and cursor_row is not None:
        cursor_y = data_start_y + cursor_row * row_h
        cursor_x = MARGIN + char_w // 2
        draw.rectangle(
            [cursor_x, cursor_y + 2, cursor_x + char_w, cursor_y + row_h - 4],
            fill=pal["bright"] + (180,),
        )

    return crt_finalize(img)


def crt_table_gif(
    headers,
    rows,
    palette="green",
    title=None,
    subtitle=None,
    font_size=72,
    col_widths=None,
    cell_colors=None,
    name="crt_table",
):
    """Generate an animated CRT table GIF.

    Args:
        headers: list of column header strings
        rows: list of lists (each row = list of cell strings)
        palette: "green" or "amber"
        title: optional title string
        subtitle: optional dim subtitle
        font_size: base font size (default 36)
        col_widths: column widths in chars (auto-calculated if None)
        cell_colors: dict of (row, col) -> (r, g, b) for color overrides
        name: output filename stem

    Returns: file path of the generated GIF
    """
    if not col_widths:
        col_widths = _auto_col_widths(headers, rows)
    rows, col_widths, row_line_counts, font_size = _reflow_for_aspect(
        headers, rows, col_widths, font_size,
        has_title=bool(title), has_subtitle=bool(subtitle),
    )

    kwargs = dict(
        headers=headers,
        rows=rows,
        col_widths=col_widths,
        palette=palette,
        title=title,
        subtitle=subtitle,
        font_size=font_size,
        cell_colors=cell_colors,
        row_line_counts=row_line_counts,
    )
    frames = []
    durations = []

    # Phase 1: Title + headers (2 frames)
    for _ in range(2):
        frames.append(_render_table_frame(**kwargs, visible_rows=0))
    durations.extend([600, 400])

    # Phase 2: Row reveal with cursor blink
    for ri in range(len(rows)):
        frames.append(
            _render_table_frame(
                **kwargs, visible_rows=ri, cursor_on=True, cursor_row=ri
            )
        )
        durations.append(250)
        frames.append(_render_table_frame(**kwargs, visible_rows=ri + 1))
        durations.append(350)

    # Phase 3: Full table with cursor blink (8 frames)
    for i in range(8):
        frames.append(
            _render_table_frame(
                **kwargs,
                visible_rows=len(rows),
                cursor_on=(i % 2 == 0),
                cursor_row=len(rows),
            )
        )
        durations.append(400)

    # Phase 4: Final hold (6 frames)
    for _ in range(6):
        frames.append(_render_table_frame(**kwargs, visible_rows=len(rows)))
        durations.append(500)

    return crt_save_gif(frames, durations, name)


def crt_table_png(
    headers,
    rows,
    palette="green",
    title=None,
    subtitle=None,
    font_size=72,
    col_widths=None,
    cell_colors=None,
    name="crt_table",
):
    """Generate a static CRT table PNG (full table, no animation).

    Same args as crt_table_gif. Returns PNG file path.
    """
    if not col_widths:
        col_widths = _auto_col_widths(headers, rows)
    rows, col_widths, row_line_counts, font_size = _reflow_for_aspect(
        headers, rows, col_widths, font_size,
        has_title=bool(title), has_subtitle=bool(subtitle),
    )
    img = _render_table_frame(
        headers=headers, rows=rows, col_widths=col_widths,
        visible_rows=len(rows), palette=palette, title=title,
        subtitle=subtitle, font_size=font_size, cell_colors=cell_colors,
        row_line_counts=row_line_counts,
    )
    return crt_save_png(img, name)


# ── Bar Chart ────────────────────────────────────────────────────


def _render_bar_frame(
    labels, values, visible_bars, palette="green", title=None, font_size=72,
    bar_progress=1.0,
):
    """Render one frame of a Tufte-styled CRT bar chart.

    Tufte principles: heavy framing rules, data-ink emphasis on bars/values,
    minimal structural ink, no gridlines.
    """
    pal = PALETTES[palette]
    font = crt_font(font_size)
    font_bold = crt_font(font_size, bold=True)
    char_w = font_size * 10 // 16
    row_h = int(font_size * 2.2)
    label_w = (max(len(str(l)) for l in labels) * char_w + MARGIN) if labels else MARGIN
    bar_max_w = 2000
    max_val = max(abs(v) for v in values) if values else 1

    img_w = label_w + bar_max_w + 3 * MARGIN
    title_h = row_h * 2 if title else 0
    img_h = len(labels) * row_h + 2 * MARGIN + title_h + row_h

    img = crt_canvas(img_w, img_h)
    draw = ImageDraw.Draw(img)

    y = MARGIN
    if title:
        draw.text(
            (MARGIN, y), title, font=font_bold, fill=pal["bright"] + (255,)
        )
        y += row_h
        y += int(row_h * 0.3)

    # ── Heavy top rule (Tufte framing) ──
    draw.line(
        [(MARGIN, y), (img_w - MARGIN, y)],
        fill=pal["bright"] + (220,), width=3,
    )
    y += 8

    bars_end_y = y
    for i, (label, val) in enumerate(zip(labels, values)):
        if i > visible_bars:
            break
        draw.text(
            (MARGIN, y + 4), str(label), font=font, fill=pal["normal"] + (255,)
        )

        full_w = int(abs(val) / max_val * bar_max_w) if max_val > 0 else 0
        bar_w = int(full_w * bar_progress) if i == visible_bars else full_w

        bx = label_w + MARGIN
        bar_color = pal["faint"] if val >= 0 else pal["ghost"]
        if bar_w > 0:
            draw.rectangle(
                [bx, y + 8, bx + bar_w, y + row_h - 10], fill=bar_color + (120,)
            )

        if i < visible_bars or bar_progress >= 1.0:
            val_str = (
                f"${val:,.0f}" if isinstance(val, (int, float)) else str(val)
            )
            draw.text(
                (bx + bar_w + 12, y + 4),
                val_str,
                font=font,
                fill=pal["bright"] + (255,),
            )

        bars_end_y = y + row_h
        y += row_h

        # Faint row separator
        if i < len(labels) - 1 and i < visible_bars:
            draw.line(
                [(MARGIN, y), (img_w - MARGIN, y)],
                fill=pal["faint"] + (40,), width=1,
            )

    # ── Heavy bottom rule (Tufte framing) ──
    if visible_bars >= len(labels) - 1:
        draw.line(
            [(MARGIN, bars_end_y + 4), (img_w - MARGIN, bars_end_y + 4)],
            fill=pal["bright"] + (220,), width=2,
        )

    return crt_finalize(img)


def crt_bar_gif(
    labels, values, palette="green", title=None, font_size=72, name="crt_bars"
):
    """Generate an animated CRT bar chart GIF.

    Args:
        labels: list of label strings
        values: list of numeric values
        palette: "green" or "amber"
        title: optional title string
        font_size: base font size
        name: output filename stem

    Returns: file path of the generated GIF
    """
    kwargs = dict(
        labels=labels, values=values, palette=palette, title=title,
        font_size=font_size,
    )
    frames = []
    durations = []

    # Title hold
    frames.append(_render_bar_frame(**kwargs, visible_bars=-1))
    durations.append(800)

    # Bars animate in with growth
    for i in range(len(labels)):
        for progress in [0.3, 0.7, 1.0]:
            frames.append(
                _render_bar_frame(**kwargs, visible_bars=i, bar_progress=progress)
            )
            durations.append(120)

    # Hold
    for _ in range(10):
        frames.append(_render_bar_frame(**kwargs, visible_bars=len(labels) - 1))
        durations.append(400)

    return crt_save_gif(frames, durations, name)


def crt_bar_png(
    labels, values, palette="green", title=None, font_size=72, name="crt_bars"
):
    """Generate a static CRT bar chart PNG. Returns PNG file path."""
    img = _render_bar_frame(
        labels=labels, values=values, visible_bars=len(labels) - 1,
        palette=palette, title=title, font_size=font_size, bar_progress=1.0,
    )
    return crt_save_png(img, name)


# ── Flow Diagram ─────────────────────────────────────────────────


def crt_box(draw, x, y, w, h, label, pal, font, level="normal"):
    """Draw a rounded box with centered label. Tufte: thin structural outline."""
    outline_color = pal["dim"] + (180,)
    text_color = pal[level] + (255,)
    draw.rounded_rectangle(
        [x, y, x + w, y + h], radius=12, outline=outline_color, width=2
    )
    bbox = font.getbbox(label)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (x + (w - tw) // 2, y + (h - th) // 2), label, font=font, fill=text_color
    )


def crt_arrow(draw, x1, y1, x2, y2, pal, level="faint"):
    """Draw a directional arrow. Tufte: minimal structural ink."""
    color = pal[level] + (200,)
    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 32
    draw.polygon(
        [
            (x2, y2),
            (
                x2 - size * math.cos(angle - 0.35),
                y2 - size * math.sin(angle - 0.35),
            ),
            (
                x2 - size * math.cos(angle + 0.35),
                y2 - size * math.sin(angle + 0.35),
            ),
        ],
        fill=color,
    )


def _auto_layout_boxes(labels, font, font_size):
    """Auto-calculate box positions and canvas size from labels.

    Accepts either:
      - list of label strings (auto-layout)
      - list of (x, y, w, h, label) tuples (pass-through)

    Returns (boxes, img_w, img_h) where boxes = [(x, y, w, h, label), ...].
    """
    if labels and isinstance(labels[0], (list, tuple)):
        # Already positioned — just compute canvas from bounds
        boxes = labels
        max_x = max(bx + bw for bx, by, bw, bh, _ in boxes)
        max_y = max(by + bh for bx, by, bw, bh, _ in boxes)
        return boxes, max_x + MARGIN * 2, max_y + MARGIN * 2

    # Auto-layout: measure each label, size boxes, stack vertically
    pad_x = int(font_size * 2.0)  # padding inside box
    pad_y = int(font_size * 1.2)
    gap = int(font_size * 2.0)    # gap between boxes (arrow space)

    box_sizes = []
    for label in labels:
        bbox = font.getbbox(label)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        box_sizes.append((bw, bh, label))

    # Title area
    title_h = int(font_size * 3.5)

    # Uniform box width + height
    max_w = max(bw for bw, _, _ in box_sizes)
    max_h = max(bh for _, bh, _ in box_sizes)
    box_sizes = [(max_w, max_h, label) for _, _, label in box_sizes]

    img_w = max_w + MARGIN * 2
    total_h = title_h + len(box_sizes) * max_h + (len(box_sizes) - 1) * gap + MARGIN * 2
    img_h = total_h

    boxes = []
    y = title_h + MARGIN
    cx = MARGIN + max_w // 2
    for bw, bh, label in box_sizes:
        bx = cx - bw // 2
        boxes.append((bx, y, bw, bh, label))
        y += bh + gap

    return boxes, img_w, img_h


def crt_diagram_gif(
    labels, title=None, palette="green", font_size=56,
    img_w=None, img_h=None, name="crt_diagram",
):
    """Generate animated flow diagram GIF.

    Args:
        labels: list of label strings OR list of (x, y, w, h, label) tuples.
        title: optional title
        palette: "green" or "amber"
        font_size: font size for box labels
        img_w, img_h: canvas dimensions (auto-calculated if None)
        name: output filename stem

    Returns: file path of the generated GIF
    """
    pal = PALETTES[palette]
    font = crt_font(font_size)
    font_bold = crt_font(font_size + 6, bold=True)
    boxes, auto_w, auto_h = _auto_layout_boxes(labels, font, font_size)
    img_w = img_w or auto_w
    img_h = img_h or auto_h

    frames = []
    durations = []

    for visible in range(len(boxes) + 1):
        img = crt_canvas(img_w, img_h)
        draw = ImageDraw.Draw(img)

        if title:
            draw.text(
                (MARGIN, MARGIN), title, font=font_bold, fill=pal["bright"] + (255,)
            )
            draw.line(
                [(MARGIN, MARGIN + font_size + 20), (img_w - MARGIN, MARGIN + font_size + 20)],
                fill=pal["dim"] + (255,), width=2,
            )

        for i in range(visible):
            bx, by, bw, bh, label = boxes[i]
            crt_box(draw, bx, by, bw, bh, label, pal, font)
            if i > 0:
                px, py, pw, ph, _ = boxes[i - 1]
                crt_arrow(draw, px + pw // 2, py + ph, bx + bw // 2, by, pal)

        frames.append(crt_finalize(img))
        durations.append(500)

    # Hold final
    for _ in range(8):
        frames.append(frames[-1])
        durations.append(400)

    return crt_save_gif(frames, durations, name)


def crt_diagram_png(
    labels, title=None, palette="green", font_size=56,
    img_w=None, img_h=None, name="crt_diagram",
):
    """Generate a static CRT flow diagram PNG.

    Args:
        labels: list of label strings OR list of (x, y, w, h, label) tuples.
        title: optional title
        palette: "green" or "amber"
        font_size: font size for box labels
        img_w, img_h: canvas dimensions (auto-calculated if None)
        name: output filename stem

    Returns: PNG file path
    """
    pal = PALETTES[palette]
    font = crt_font(font_size)
    font_bold = crt_font(font_size + 6, bold=True)
    boxes, auto_w, auto_h = _auto_layout_boxes(labels, font, font_size)
    img_w = img_w or auto_w
    img_h = img_h or auto_h

    img = crt_canvas(img_w, img_h)
    draw = ImageDraw.Draw(img)

    if title:
        draw.text(
            (MARGIN, MARGIN), title, font=font_bold, fill=pal["bright"] + (255,)
        )
        draw.line(
            [(MARGIN, MARGIN + font_size + 20), (img_w - MARGIN, MARGIN + font_size + 20)],
            fill=pal["dim"] + (255,), width=2,
        )

    for i, (bx, by, bw, bh, label) in enumerate(boxes):
        crt_box(draw, bx, by, bw, bh, label, pal, font)
        if i > 0:
            px, py, pw, ph, _ = boxes[i - 1]
            crt_arrow(draw, px + pw // 2, py + ph, bx + bw // 2, by, pal)

    return crt_save_png(crt_finalize(img), name)


# ── Telegram posting ──────────────────────────────────────────────


def send_crt_photo(png_path, token, chat_id, thread_id=None, caption=None, reply_to=None):
    """Send PNG to Telegram via sendPhoto with retry. Returns parsed JSON response."""
    import json
    import urllib.error
    import urllib.request
    from pathlib import Path

    # Telegram caption limit is 1024 chars
    if caption and len(caption) > 1024:
        caption = caption[:1021] + "..."

    boundary = "----CRTBoundary"

    def _build_body():
        body = bytearray()

        def add_field(name, value):
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            )
            body.extend(f"{value}\r\n".encode())

        add_field("chat_id", chat_id)
        if thread_id:
            add_field("message_thread_id", thread_id)
        if reply_to:
            add_field("reply_to_message_id", reply_to)
        if caption:
            add_field("caption", caption)
            add_field("parse_mode", "HTML")

        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            b'Content-Disposition: form-data; name="photo"; filename="crt.png"\r\n'
        )
        body.extend(b"Content-Type: image/png\r\n\r\n")
        body.extend(Path(png_path).read_bytes())
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body)

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = _build_body()

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data)
            req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                import time as _time
                retry_after = int(e.headers.get("Retry-After", "5"))
                _time.sleep(retry_after)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                import time as _time
                _time.sleep(2)
                continue
            raise


# Keep old name as alias
send_crt_gif = send_crt_photo


# ── Distribution Box Plot ────────────────────────────────────────


def crt_distribution_png(
    percentiles: dict,
    title: str = "P&L DISTRIBUTION",
    subtitle: str = "",
    palette: str = "cyan",
    font_size: int = 72,
    name: str = "mc_dist",
    initial_capital: float = 100_000.0,
    negative_pct: float = 0.0,
    verdict_label: str = "",
) -> str:
    """Render a horizontal box-and-whisker distribution chart as CRT PNG.

    percentiles: dict with keys "p5", "p25", "median", "p75", "p95" (float values).
    Draws p5--p95 range bar, filled IQR box (p25--p75), bright median line,
    and labeled percentile values below. Verdict line if p5 > 0.

    verdict_label: if provided, use this exact verdict label instead of re-deriving.

    Returns: PNG file path.
    """
    pal = PALETTES[palette]
    font = crt_font(font_size)
    font_bold = crt_font(font_size, bold=True)
    font_small = crt_font(font_size - 12)
    char_w = font_size * 10 // 16

    p5 = percentiles.get("p5", 0)
    p25 = percentiles.get("p25", 0)
    median = percentiles.get("median", 0)
    p75 = percentiles.get("p75", 0)
    p95 = percentiles.get("p95", 0)

    # Layout dimensions
    plot_margin_left = MARGIN + char_w * 2
    plot_margin_right = MARGIN + char_w * 2
    plot_w = 2400
    img_w = plot_margin_left + plot_w + plot_margin_right

    row_h = int(font_size * 2.0)
    title_h = row_h if title else 0
    sub_h = row_h if subtitle else 0
    gap_h = int(row_h * 0.5) if (title or subtitle) else 0
    bar_h = int(font_size * 3.0)
    label_h = int(row_h * 2.5)
    verdict_h = row_h * 2
    rule_gap_top = int(row_h * 0.4)
    rule_gap_bot = int(row_h * 0.3)
    img_h = MARGIN + title_h + sub_h + gap_h + rule_gap_top + bar_h + label_h + rule_gap_bot + verdict_h + MARGIN

    img = crt_canvas(img_w, img_h)
    draw = ImageDraw.Draw(img)
    y = MARGIN

    # Title
    if title:
        draw.text((MARGIN, y), title, font=font_bold, fill=pal["bright"] + (255,))
        y += title_h
    # Subtitle
    if subtitle:
        draw.text((MARGIN, y), subtitle, font=font_small, fill=pal["dim"] + (255,))
        y += sub_h
    if title or subtitle:
        y += gap_h

    # Heavy top rule
    draw.line(
        [(MARGIN, y), (img_w - MARGIN, y)],
        fill=pal["bright"] + (220,), width=3,
    )
    y += int(row_h * 0.4)

    # Map data values to pixel x positions — pad narrow distributions
    data_min = p5
    data_max = p95
    data_range = data_max - data_min
    # Ensure minimum visual range: at least 1% of capital or $100, whichever is larger
    min_range = max(initial_capital * 0.01, 100.0)
    if data_range < min_range:
        mid = (data_min + data_max) / 2.0
        data_min = mid - min_range / 2.0
        data_max = mid + min_range / 2.0
        data_range = min_range

    def val_to_x(v: float) -> int:
        frac = (v - data_min) / data_range
        return int(plot_margin_left + frac * plot_w)

    x_p5 = val_to_x(p5)
    x_p25 = val_to_x(p25)
    x_med = val_to_x(median)
    x_p75 = val_to_x(p75)
    x_p95 = val_to_x(p95)

    bar_top = y + bar_h // 4
    bar_bot = y + bar_h - bar_h // 4
    bar_mid = y + bar_h // 2

    # Whisker line: p5 to p95 (thin, dim)
    whisker_y = bar_mid
    draw.line(
        [(x_p5, whisker_y), (x_p95, whisker_y)],
        fill=pal["dim"] + (200,), width=3,
    )
    # Whisker caps (vertical)
    cap_h = bar_h // 4
    draw.line(
        [(x_p5, whisker_y - cap_h), (x_p5, whisker_y + cap_h)],
        fill=pal["dim"] + (200,), width=3,
    )
    draw.line(
        [(x_p95, whisker_y - cap_h), (x_p95, whisker_y + cap_h)],
        fill=pal["dim"] + (200,), width=3,
    )

    # IQR box: p25 to p75 (filled, faint)
    draw.rectangle(
        [x_p25, bar_top, x_p75, bar_bot],
        fill=pal["faint"] + (100,),
        outline=pal["normal"] + (200,),
        width=2,
    )

    # Median line (bright, vertical through box)
    draw.line(
        [(x_med, bar_top - 4), (x_med, bar_bot + 4)],
        fill=pal["bright"] + (255,), width=5,
    )

    # Zero line if range spans zero
    if p5 < 0 < p95:
        x_zero = val_to_x(0)
        draw.line(
            [(x_zero, bar_top - 10), (x_zero, bar_bot + 10)],
            fill=(255, 60, 60, 120), width=2,
        )
        zero_label = "$0"
        small_char_w = (font_size - 12) * 10 // 16
        draw.text(
            (x_zero - len(zero_label) * small_char_w // 2, bar_bot + 14),
            zero_label, font=font_small, fill=(255, 60, 60, 180),
        )

    y += bar_h

    # Percentile labels below the chart
    label_y = y + int(font_size * 0.3)

    def _fmt_val(v: float) -> str:
        sign = "+" if v >= 0 else "-"
        av = abs(v)
        if av >= 1_000_000:
            return f"{sign}${av/1_000_000:,.1f}M"
        if av >= 1000:
            return f"{sign}${av/1000:,.1f}K"
        return f"{sign}${av:,.0f}"

    pct_items = [
        ("p5", p5, x_p5, pal["dim"]),
        ("p25", p25, x_p25, pal["normal"]),
        ("MEDIAN", median, x_med, pal["bright"]),
        ("p75", p75, x_p75, pal["normal"]),
        ("p95", p95, x_p95, pal["dim"]),
    ]

    # Compute label positions and resolve overlaps (left-to-right sweep)
    small_cw = (font_size - 12) * 10 // 16
    label_positions = []
    for label_text, val, x_pos, color in pct_items:
        val_str = _fmt_val(val)
        lbl_w = len(max(label_text, val_str, key=len)) * small_cw
        label_positions.append((x_pos, lbl_w, label_text, val, color))

    min_gap = small_cw  # 1 character gap
    resolved = []
    for i, (x, w, lt, v, c) in enumerate(label_positions):
        if resolved:
            prev_x, prev_w = resolved[-1][0], resolved[-1][1]
            min_x = prev_x + prev_w // 2 + w // 2 + min_gap
            if x < min_x:
                x = min_x
        resolved.append((x, w, lt, v, c))

    for x_pos, _, label_text, val, color in resolved:
        val_str = _fmt_val(val)
        lbl_w = len(label_text) * small_cw
        val_w = len(val_str) * small_cw
        draw.text(
            (x_pos - lbl_w // 2, label_y),
            label_text, font=font_small, fill=color + (180,),
        )
        draw.text(
            (x_pos - val_w // 2, label_y + int(font_size * 0.9)),
            val_str, font=font_small, fill=color + (255,),
        )

    y += label_h

    # Heavy bottom rule
    draw.line(
        [(MARGIN, y), (img_w - MARGIN, y)],
        fill=pal["bright"] + (220,), width=2,
    )
    y += int(row_h * 0.3)

    # Verdict line — use caller's label if provided, else derive from data
    vl = verdict_label.upper() if verdict_label else ""
    if vl == "ROBUST" or (not vl and p5 > 0 and negative_pct < 5):
        verdict_color = (0, 255, 65)  # bright green
        verdict_text = "EDGE CONFIRMED: worst-case p5 still profitable"
    elif vl == "MODERATE" or (not vl and median > 0 and p5 > -(initial_capital * 0.01)):
        verdict_color = pal["normal"]
        verdict_text = "MODERATE: median positive, p5 near break-even"
    elif vl == "FRAGILE" or (not vl and median > 0):
        verdict_color = (255, 176, 0)  # amber
        verdict_text = "FRAGILE: profitable median but risky tail"
    elif vl == "INSUFFICIENT DATA":
        verdict_color = pal["dim"]
        verdict_text = "INSUFFICIENT DATA"
    else:
        verdict_color = (255, 60, 60)  # red
        verdict_text = "NO EDGE: median not profitable"
    draw.text(
        (MARGIN, y), verdict_text, font=font_bold, fill=verdict_color + (255,),
    )

    return crt_save_png(crt_finalize(img), name)


# ── Demo ──────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=== CRT Table Demo ===")
    crt_table_gif(
        headers=["Tier", "Trades", "Win Rate", "Avg P&L", "Total P&L"],
        rows=[
            ["Diamond", "43", "100%", "$32.44", "+$1,395"],
            ["Gold", "272", "99.6%", "$34.11", "+$9,278"],
            ["Silver", "362", "99.7%", "$32.06", "+$11,606"],
            ["Bronze", "1,311", "100%", "$7.91", "+$10,372"],
        ],
        palette="green",
        title="CONVICTION TIER PERFORMANCE",
        name="demo_table",
    )

    print("\n=== CRT Bar Chart Demo ===")
    crt_bar_gif(
        labels=["Diamond", "Gold", "Silver", "Bronze"],
        values=[1395, 9278, 11606, 10372],
        palette="amber",
        title="P&L BY TIER",
        name="demo_bars",
    )

    print("\n=== CRT Diagram Demo ===")
    crt_diagram_gif(
        labels=[
            (40, 160, 140, 50, "Platform\nPolling"),
            (240, 160, 140, 50, "Whale\nDetection"),
            (440, 160, 140, 50, "Conviction\nScoring"),
            (640, 160, 140, 50, "Paper\nTrading"),
            (840, 160, 120, 50, "P&L\nTopic"),
        ],
        title="SIGNAL PIPELINE",
        palette="green",
        name="demo_pipeline",
    )
