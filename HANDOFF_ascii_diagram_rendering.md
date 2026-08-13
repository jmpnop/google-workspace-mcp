# Handoff — ASCII / box-drawing diagram rendering fix

**Re:** `AGENT_REQUEST_ascii_diagram_rendering.md`
**Status:** ✅ Complete and verified end-to-end (code uncommitted on `main`).
**Component:** `plugin/gdocs_tufte_plugin` (Tufte publisher, Phase-6 image pipeline).

---

## TL;DR

Box-drawing diagrams published by `publish_markdown_tufte` sheared because characters
were placed by the rasterizer's own glyph advances and it silently substituted fonts for
glyphs JetBrains Mono didn't resolve. Rewrote the `ascii_svg` path to render each glyph as
a **vector `<path>` outline on an explicit monospace grid** — deterministic and independent
of any rasterizer/host font. Along the way, live-publish validation surfaced and fixed two
more defects in the *publishing* layer (cache collision, caption gluing).

Everything is validated against the **actual published Google Docs** (Docs API + PDF), not
just local renders.

---

## Root cause & why the chosen fix (verified empirically, not assumed)

The request suggested (a) an explicit grid and (b) embedding the font via base64
`@font-face`. I preflight-tested against the **real** rasterizer on this host
(`rsvg-convert` / librsvg 2.62, first in `gdocs/docs_svg.py:_svg_to_png_bytes`):

- **librsvg ignores `@font-face`.** An embedded-font SVG rendered with spread-out text and
  dashed box lines — so suggestion (b) does **not** work with the production rasterizer.
- Name-only `font-family` "worked" on this machine only because JetBrains Mono happens to
  be installed system-wide; it would break on any deploy box without it, and for glyphs the
  substitute font lacks (per-glyph fallback → mixed advances → shear).

**Chosen fix: vector glyph outlines on an explicit grid.** Each char is emitted as
`<path transform="translate(x,y)" d=…>` where `x = PAD + col*CHAR_W`,
`baseline = PAD + (row+1)*LINE_H`, and `CHAR_W` is the **measured** advance
(600/1000 em → 8.4px at 14px, not the old guessed 9.6). No `<text>`, no font resolution at
raster time → byte-identical output on macOS/Linux/cairosvg/resvg/Chrome. All box/arrow
glyphs (incl. `▼►▲◄`, double/heavy `═║╔╣╬`) verified present in the vendored font.

---

## Files changed

| File | Change |
|---|---|
| `plugin/gdocs_tufte_plugin/render/ascii_svg.py` | **NEW** — vector-grid renderer (fontTools outline extraction, measured pitch, resilient fallback, tab expansion, `RENDER_VERSION`). |
| `plugin/gdocs_tufte_plugin/tufte_publisher.py` | `_ascii_art_to_svg` delegates to the new renderer; Phase-6 aspect uses `ascii_svg_dimensions`; `_diagram_cache_key` (style-aware); image inserted in its own paragraph. |
| `plugin/pyproject.toml` | + `fonttools>=4.0`. |
| `plugin/tests/test_ascii_svg.py` | **NEW** — 15 tests. |
| `uv.lock` | fonttools resolved (4.63.0). |

## All defects fixed

1. **Shear/misalignment (the request).** Deterministic vector grid. `render/ascii_svg.py`.
2. **Wrong metric.** `CHAR_W` measured (8.4) not guessed (9.6); Phase-6 image aspect uses
   the same source of truth so the placed image isn't distorted.
3. **Resilience (from adversarial review).** `char_width()`/`ascii_svg_dimensions` no longer
   raise on a broken font env (fall back to nominal pitch → publish never hard-fails);
   the text fallback uses the same pitch as the dimension math (no ~14% aspect skew); tabs
   are expanded so they can't collapse a column.
4. **Image cache collision (found in live publish).** Cache key was `art+version` but not
   style → classic & CRT shared one image (CRT got the white classic PNG). Now
   `_diagram_cache_key` = `render_version + style.name + art`.
5. **Caption gluing (the "still has issues" the user saw).** Phase-6 inserted the image
   inline at the start of the following paragraph → caption stranded beside the diagram on
   wide/CRT layouts. Now inserted in its own paragraph (verified: image at `[271-273]`,
   caption separate at `[273-387]`).

---

## Verification (done-when checklist)

- [x] **Repro renders correctly, classic AND CRT** — exact repro (extracted verbatim from
  the request) rendered through the real pipeline; every `│`/`▼` sits under its `┬`/`┼`,
  runs meet corners. Confirmed in-process AND via the **published Google Docs' exported
  PDFs**.
- [x] **Regression test / grid invariant** — `plugin/tests/test_ascii_svg.py` (15 passing):
  grid invariant (one x per column across all rows), measured char-width, pure-vector /
  no-`<text>`, glyph coverage, tab expansion, font-failure fallback, fallback aspect ==
  dimensions, style-aware cache key, and an end-to-end pixel-alignment golden.
- [x] **No regression to `render_tufte_graphic`** — its `diagram` type uses
  `crt_raster.crt_diagram_png` (Pillow), a separate path that was not touched.
- [x] **Full suite:** 180 passed.
- [x] **Independent review:** two adversarial agents (correctness + integration/packaging)
  confirmed the renderer geometry/winding/tiling by pixel-sampling and verified the wheel
  ships `ascii_svg.py` + the fonts; their findings were all addressed.

**Validation docs (safe to delete):**
- Classic — https://docs.google.com/document/d/1P73guC52h9hfTNhjED_7DV1fV2MQbi2zakNjyvTIF7w/edit
- CRT — https://docs.google.com/document/d/1-zrWbNTb0GeZfgPkcogQBWmFZFAje7oWZY8l3fMe5ck/edit

---

## Operational state

- The MCP server is **launchd-managed** (`io.celestialtech.google-workspace-mcp`,
  KeepAlive+RunAtLoad, plugin installed editable from source). Restart with:
  `launchctl kickstart -k gui/$(id -u)/io.celestialtech.google-workspace-mcp`.
- It has been restarted and is **running the final code**. The plugin is editable, so a
  restart is required to load any further plugin edits (Python doesn't hot-reload).

## Open items / follow-ups

1. **Commit.** All changes are uncommitted on `main`. Suggested: branch + commit the new
   module, publisher edits, `pyproject.toml`, tests, `uv.lock`. (No AI attribution in the
   message, per repo convention.)
2. **Original PolyWhale doc** (`1dJiIo3Vemrga_pYMGrvypVT_c-5dNSan2RolbgMxR0E`) still shows
   the old broken diagram — its source markdown wasn't available. Re-publish in place
   (`doc_id=…`) once the source is provided.
3. **Consciously deferred (low value):** the public `ascii_art_to_svg(ink_hex,bg_hex)` args
   aren't validated/escaped (all internal callers pass trusted `#RRGGBB`); and
   `_svg_to_png_bytes` depends on `rsvg-convert`/`cairosvg` being present on the host — a
   **pre-existing** requirement, not introduced here, and not declared as a plugin dep.

## How to re-validate quickly

```bash
uv run python -m pytest plugin/tests/test_ascii_svg.py -q      # 15 pass
# End-to-end: publish → inspect the PUBLISHED doc, not just the PNG
#   - Docs API documents.get -> check inlineObjects + which paragraph holds the image
#     (inspect_doc_structure does NOT surface inline images)
#   - export_doc_to_pdf -> download via authenticated Drive files().get_media
#     (NOT uc?export=download, which returns a virus-scan HTML page) -> view the PDF
# Stored creds: ~/.google_workspace_mcp/credentials/<email>.json
```
