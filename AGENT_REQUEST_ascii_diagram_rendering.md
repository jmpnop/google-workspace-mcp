# Agent request — fix badly-formatted ASCII / box-drawing diagrams in `publish_markdown_tufte`

**Filed:** 2026-08-10 · **Component:** `plugin/gdocs_tufte_plugin` (Tufte publisher, Phase 6 image pipeline)
**Severity:** high (user-visible — every doc with a data-flow / box-drawing diagram renders broken)

---

## Symptom

When a markdown source contains a fenced code block with box-drawing / ASCII art (data-flow diagrams,
etc.), `publish_markdown_tufte` renders it to a PNG whose **columns drift out of alignment** — vertical
`│` connectors don't line up under `┬`/`┴`, horizontal `───` runs don't meet their corners `┐`/`┘`, and
boxes look sheared/ragged. Reproduced live in the "PolyWhale Architecture" doc
(`1dJiIo3Vemrga_pYMGrvypVT_c-5dNSan2RolbgMxR0E`), classic style.

## Repro (the exact diagram that broke)

````
        Platform APIs (REST)            Polygon blockchain (OrderFilled / CTF)
              │                                    │
              ▼                                    ▼
   ┌──────────────────────────── PolyWhaleRecorder (Swift / macOS) ───────────────────────────┐
   │  per-platform adapters · whale-signal detection · category+resolution capture · gap fill  │
   └───────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │  writes
                                                ▼
        <platform>_hot.sqlite   ── bounded ingest buffers (trades 48h · snapshots 30d)
                                                │
                                                ▼
        DuckDB / Parquet lake    ── AUTHORITATIVE archive
                                                │
              ┌─────────────────────────────────┼───────────────────────────────────────┐
              ▼                                 ▼                                         ▼
        pw_engine                          plwhl_bot                                  plwhl_web
````

Any box-art with wide horizontal runs + aligned columns shows the drift; the wider the diagram, the worse.

## Root cause (verified in the code)

`_ascii_art_to_svg(art, style)` — `plugin/gdocs_tufte_plugin/tufte_publisher.py:1274`:

```python
line_height = 18
char_width  = 9.6  # "Approximate for JetBrains Mono at 14px"   ← wrong metric (see below)
...
for i, line in enumerate(lines):
    ...
    text_elements.append(
        f'  <text x="20" y="{y}" '
        f'font-family="JetBrains Mono, Menlo, monospace" '
        f'font-size="14" fill="{text_fill}" '
        f'xml:space="preserve">{escaped}</text>')
```

Two compounding defects:

1. **No fixed grid — horizontal positions come *only* from the font's glyph advances.** Each source line
   is emitted as a single `<text>` string; the renderer places character *N* wherever the cumulative
   advance of characters 0..N-1 lands. This is correct *only if* every glyph (including box-drawing
   `─ │ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ▼ ► ▲ ◄`) advances by exactly the same width **and** that width is identical on
   every line. Any per-glyph advance difference accumulates across a wide line, so lower/upper rows shear
   relative to each other → broken boxes. `xml:space="preserve"` keeps leading spaces but does nothing for
   advance drift.

2. **The rasterizing font is not guaranteed to be the vendored monospace.** The SVG is rasterized by
   `_svg_to_png_bytes` (`gdocs/docs_svg.py`). If that rasterizer (rsvg-convert / resvg / Chrome) does not
   have **JetBrains Mono** registered, it falls back to `Menlo` → generic `monospace`, whose box-drawing
   metrics differ from the assumed grid. The plugin *vendors* JetBrains Mono in `plugin/gdocs_tufte_plugin/fonts/`
   but the SVG references it only by `font-family` name (no `@font-face`), so the rasterizer likely never
   loads it. (Also: JetBrains Mono's advance at 14px is ~**8.4px** (600/1000 em), not the hardcoded `9.6` —
   evidence the metric was guessed, not measured; `9.6` is currently used only for the canvas width, but it
   confirms the grid math is untethered from the actual font.)

## Required fix (root cause / whole class — not a nudge to `char_width`)

Make box-art render on a **deterministic monospace grid, independent of the rasterizer's font choice.** Do
**both**:

**(a) Place characters on an explicit grid.** Instead of one `<text>` per line relying on natural advance,
position each cell at `x = PAD + col * CHAR_W`, `y = PAD + (row+1) * LINE_H`. Simplest robust form: emit
one `<text>` per line but force its width with `textLength="{n_cols * CHAR_W}" lengthAdjust="spacingAndGlyphs"`,
which pins the line to exactly `n_cols * CHAR_W` regardless of the font. (Per-character `<tspan x=…>` is the
gold standard if `textLength` distortion is visible on box glyphs — evaluate both.) Compute `n_cols` as the
character count (with `xml:space="preserve"` so leading spaces count).

**(b) Guarantee the exact font is embedded in the SVG** so the rasterizer can't substitute: inline the
vendored JetBrains Mono as a base64 `@font-face` in the SVG `<defs><style>` and reference that family. Then
**measure** the true advance for that font at 14px and set `CHAR_W`/`LINE_H` from the measured metrics (a
one-line freetype/fontTools probe), not a guess. Verify all `_BOX_CHARS` (`tufte_publisher.py:91`) exist in
the embedded font (JetBrains Mono covers the light box-drawing set; confirm `▼►▲◄` and any heavy/double
`═║╔…` used).

## Files

- `plugin/gdocs_tufte_plugin/tufte_publisher.py` — `_ascii_art_to_svg` (~1274), the Phase-6 width/height
  math (~1245), `_detect_ascii_art_blocks` (~97), `_BOX_CHARS` (~91).
- `gdocs/docs_svg.py` — `_svg_to_png_bytes` (rasterizer + whether it registers fonts).
- `plugin/gdocs_tufte_plugin/fonts/` — the vendored JetBrains Mono to embed.

## Verification / done-when

1. Re-publish the repro diagram above (classic **and** a CRT style) and confirm every `│` aligns under its
   `┬`/`┼`, and horizontal runs meet their corners exactly (eyeball at 100%).
2. Add a **golden-image / pixel test**: render a small fixed box-art fixture to PNG and assert against a
   committed reference (or assert grid invariants — e.g., the x-pixel of column *c* is identical on every
   row). This class of regression must be caught automatically going forward.
3. Confirm no regression to the `render_tufte_graphic` designed illustrations (the HTML `illustration`
   renderer is a separate path and should be untouched).

## Notes / non-goals

- Do **not** "solve" this by pre-converting the ASCII to prose or dropping diagrams — box-art rendering is a
  first-class feature.
- The `illustration` (HTML/CSS→Chrome) and `crt_raster` (Pillow) renderers are separate; this bug is
  specifically the **`ascii_svg` vector path** used for raw box-drawing fences.
