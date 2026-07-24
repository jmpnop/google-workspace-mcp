# Tufte via Google Docs MCP — Consolidation Plan (Plugin Architecture)

**Goal:** collapse the scattered Tufte/CRT Google-Docs capability into **one Claude Code plugin** — a shared Python library + a single skill — that attaches to `google-workspace-mcp` through a **minimal, upstreamable extension seam**, so the fork stops carrying Tufte drift in its core and can track upstream cleanly.

Status: **✅ IMPLEMENTED** — branch merged to the fork's `main`. This document is both the design and the shipped record; the sections below describe what was built. Grounded in a 5-agent code audit (findings inline with `file:line` evidence).

### Shipped

| Phase | What | Verified |
|---|---|---|
| 1 · Seam | `workspace_mcp.tools` entry-point scan (`main.py`, `fastmcp_server.py`) | plugin discovered |
| 2 · Extract | Tufte moved to `plugin/gdocs_tufte_plugin`; dropped from core `docs` group | tool registers via seam; core `gdocs.tufte_tools` gone |
| 3 · Raster | `render/crt_raster.py` + vendored fonts (package-relative) | near-black canvas + phosphor render |
| 4 · Highlighter | `syntax.py` (rust/sql/json/toml/sh) wired into the code-block phase | real CRT publish: `#010101` bg + phosphor keywords |
| 5 · Illustration | `render/illustration.py` (HTML/CSS → Chro **CDP**/CLI → trim) | light Tufte-Classic panel at 2× |
| 6 · Render tool | `render_tufte_graphic` (table/bar/diagram/distribution → PNG → Drive) | registers via seam |
| 7 · Skill + registry | one `gdocs-tufte` skill; live in `jmpnop/registry` | `/plugin install gdocs-tufte@registry` |

- Fork PR `jmpnop/google-workspace-mcp#1` — **merged**. Upstream seam PR `taylorwilsdon/google_workspace_mcp#960` — open.
- Go-live: install the plugin + restart the server, then remove the three loose `gdocs-tufte*` skills (superseded).

**Execution note:** the audit swarm ran as fire-and-await `Agent` tasks; two of them ran **~55 h** before returning. Any follow-up build-out swarm must go through the **`leashed-swarm`** skill (bounded rounds + bash supervisor + `Monitor`), not unleashed `Agent`/`Workflow` loops.

---

## 0. The decision, up front

1. **`google-workspace-mcp` is a fork** of `taylorwilsdon/google_workspace_mcp` (remotes: `origin`=upstream, `mine`=jmpnop; merge-base `9631b9e`). Every Tufte file is **fork-local drift** in core.
2. **There is no plugin system today.** Tools register as import-time side-effects of `@server.tool()` on a module-level `FastMCP` singleton (`core/server.py:57`); the only registration path is a **hardcoded `tool_imports` dict** (`main.py:237`), and Tufte is wired in by one line inside the `docs` lambda (`main.py:241`).
3. **The seam is tiny.** Because `server` is an importable singleton and registration is a pure import side-effect, a `~7-line entry_points(group="workspace_mcp.tools")` scan at `main.py:318` lets any pip-installed package contribute tools with **zero further core edits**. This is the *only* core change — and it should be **contributed upstream** so the fork can drop its Tufte additions and de-fork.
4. **Therefore:** move all Tufte/CRT/illustration/journal logic out of core into a **separate plugin package**, delivered as a Claude Code plugin that bundles the MCP tool(s) **and** the skill together (the discord/telegram pattern), registered in `jmpnop/registry`.

---

## 1. Fragmentation map (audited)

Same capability, **six** homes, **three** renderers, **two** full publishers, **two** divergent CRT palettes:

| # | Home | Role | Renderer | Evidence |
|---|------|------|----------|----------|
| 1 | `google_workspace_mcp/gdocs/tufte_*` (+ `docs_svg.py`) | MCP tool `publish_markdown_tufte` + 9-phase pipeline; styles classic/makarina/crt/-a/-g | ASCII→**SVG** (vector) | fork-added; wired at `main.py:241` |
| 2 | `polywhale/agents/crt_render.py` (main tree, 41 KB, Pillow) | raster tables/bars/flow/distribution + **true CRT effects** (glow/scanlines/vignette) | **Pillow raster** | `crt_render.py:63` `crt_finalize`; PALETTES `:23` |
| 3 | `polywhale/agents/generate_pipeline_doc.py` (72 KB, raw googleapiclient) | **second** full CRT-doc publisher; built the live CRT docs | raw Docs API + **rsvg-convert** SVGs | phases at `:848–1486`; `_render_svg` `:479` |
| 4 | `polywhale/agents/sentinel_common.py` | tab-journaling into a Doc (deprecated — hit the cap) | Docs REST via `urllib` | `DOC_ID` `:19`; tabs `:264`; append `:430` |
| 5 | `tufte-illustration` (repo = the installed skill, 5 files) | Tufte **Classic** editorial illustrations | HTML/CSS → **Chromium** → Pillow-trim → PNG | `render.sh:22–43`; `trim.py` |
| 6 | `~/.claude/skills/gdocs-tufte{,-classic,-crt}` | 3 prose skills, all driving one tool by `style` enum | — | all call `mcp__google__publish_markdown_tufte` |

**Duplication that must collapse:**
- **Two publishers** (`tufte_publisher.py` vs `generate_pipeline_doc.py`) — ~90% overlapping phases.
- **Three diagram renderers** (SVG in MCP; Pillow raster in `crt_render`; **rsvg-convert** SVG in `generate_pipeline_doc`) — zero code sharing.
- **Two CRT-cyan palettes** in incompatible units: `crt_render.PALETTES["cyan"]` (0–255 ints) vs `generate_pipeline_doc`'s `*_CYAN` dicts (0–1 floats). They can (and do) drift.
- **Three near-identical skills** differing only by the `style` argument.

**Corrections the audit forced (do not repeat my earlier errors):**
- **`pw-tlgrm-source` / `pw-tlgrm-sink` contain ZERO Google-Docs code.** They're local Rust crates (`polywhale/pw_tap/`, `polywhale/pw_sink/`); their reporting is Telegram + a `pw-sink status` CLI. The **sink is fully built** (`sync.rs`, `verify.rs`, `duckdb_views.rs`) — the CRT status board showing K1–K5 "Pending" was an old snapshot. **Nothing to migrate from the Rust side**; those repos contribute *spec/content*, not code.
- **Journal rollover was never built** — it was explicitly **rejected** ("never create new Google Docs"). `sentinel_common.py` blindly adds one tab/day with **no size or tab-count guard**; it died 2026-06-17 on Google's **~1.02M-char / 42-tab per-document hard cap** (every `batchUpdate insertText` 400s). That missing guard is the bug the consolidation must fix.
- **The live CRT docs' diagrams are rsvg-convert SVGs**, not `crt_render` PNGs. The two standalone `crt_*.png` Drive images came from `crt_render` (Pillow) and went to Telegram + Drive. So "CRT diagram" already means two different renderers.

---

## 2. Target architecture

A standalone plugin package — `gdocs-tufte-plugin` — is the single source of truth; core gets one tiny seam; the skill + MCP ship together as a Claude Code plugin.

```
   ┌──────────────────────── google-workspace-mcp (CORE) ────────────────────────┐
   │  UNTOUCHED except ONE upstreamable seam:                                     │
   │    main.py:318  →  entry_points(group="workspace_mcp.tools"): ep.load()      │
   │  Reused by the plugin (imported, not modified):                              │
   │    auth/service_decorator.require_multiple_services  (:719)                  │
   │    core/utils.handle_http_errors                     (:375)                  │
   │    gdocs/docs_helpers, docs_tables, docs_markdown, docs_structure            │
   │    core.server.server singleton                      (core/server.py:57)     │
   └───────────────────────────────┬─────────────────────────────────────────────┘
                                    │ entry_points + `from core.server import server`
   ┌────────────────────────────────▼────────────────────────────────────────────┐
   │                     gdocs-tufte-plugin  (NEW, separate package)              │
   │                                                                              │
   │  tufte/styles.py     TufteStyle + STYLES (classic, makarina, crt/-a/-g)      │  ← one palette source
   │  tufte/cache.py      doc_index + image-hash cache (~/.google_workspace_mcp)  │
   │  tufte/docs_api.py   batch_execute / retry / fmt_* (shared Docs helpers)     │
   │  tufte/pipeline.py   the ONE publisher (9 phases + syntax highlighting)      │
   │  tufte/journal.py    supported append mode + rollover WITH size/tab guard    │  ← fixes the dead journal
   │  tufte/render/                                                               │
   │     ascii_svg.py     vector diagrams (crisp, selectable, tiny)               │
   │     crt_raster.py    Pillow raster + glow/scanlines/vignette (from crt_render)│
   │     charts.py        bar / distribution / flow                              │
   │     illustration.py  HTML/CSS → Chro → PNG (from tufte-illustration)         │
   │  tufte/fonts/        vendored JetBrains Mono (Nerd) + Domine                 │  ← kills hardcoded paths
   │  tools.py            @server.tool() publish_markdown_tufte, render_tufte_graphic
   │  pyproject.toml      [project.entry-points."workspace_mcp.tools"]            │
   │  .claude-plugin/plugin.json   .mcp.json   skills/gdocs-tufte/SKILL.md        │  ← Claude Code plugin bundle
   └───────────────────────┬───────────────────────────┬──────────────────────────┘
                           │                           │
        ┌──────────────────┘                           └─────────────────┐
        ▼                                                                ▼
  registered in jmpnop/registry marketplace.json               PolyWhale imports the lib
  (`/plugin install gdocs-tufte@registry` → skill + MCP)        (drops crt_render.py + generate_pipeline_doc.py)
```

### 2.1 The core seam (only core change; upstream it)

Insert after the `tool_imports` loop, **before** `filter_server_tools(server)` (so tier/read-only filtering still applies), at ~`main.py:318`:

```python
from importlib.metadata import entry_points
for ep in entry_points(group="workspace_mcp.tools"):
    try:
        ep.load()                       # importing runs the module's @server.tool() decorators
        safe_print(f"   🔌 Plugin loaded: {ep.name}")
    except Exception as exc:            # noqa: BLE001
        logger.error("Failed to load plugin '%s': %s", ep.name, exc, exc_info=True)
```

Plugin declares in its own `pyproject.toml`:
```toml
[project.entry-points."workspace_mcp.tools"]
gdocs_tufte = "gdocs_tufte_plugin.tools"   # module doing `from core.server import server; @server.tool()`
```
**Contribute this seam upstream** (`taylorwilsdon/google_workspace_mcp`). If accepted, the fork rebases onto upstream and **deletes all six fork-added Tufte files from core** — the fork disappears.

### 2.2 Three renderers, one interface

`render(spec, style) -> bytes` behind a common facade; style-driven default, per-call override (`diagrams="auto|svg|crt-raster|illustration"`):

| Renderer | Backend | Deps | Default for | From |
|---|---|---|---|---|
| `ascii_svg` | pure-Python SVG→PNG | none / cairosvg | classic diagrams (crisp, selectable) | MCP `_ascii_art_to_svg`, `docs_svg.py` |
| `crt_raster` + `charts` | Pillow | Pillow | CRT styles (glow/scanlines/vignette; bars, distribution) | `polywhale/crt_render.py` |
| `illustration` | HTML/CSS → headless **Chro** → trim | **Chro** (`/Applications/Chro.app`) + Pillow | rich editorial classic panels | `tufte-illustration` |

**Shared across all three:** the `styles.py` token registry (one palette source — kills the two divergent cyan defs), **vendored fonts** (JetBrains Mono + Domine — kills the `ghostty-source` hardcoded path and the network Domine fetch), Drive upload, and the generic RGB trim step. Chro is a **declared dependency** for `illustration` (detected at `/Applications/Chro.app`), not a degrade-if-absent optional; `rsvg-convert` is **dropped** (replaced by `ascii_svg`).

---

## 3. What consolidates in (and the traps to fix)

| Source | Moves to | Preserve | Fix on the way in |
|---|---|---|---|
| `gdocs/tufte_publisher.py` (9 phases) | `tufte/pipeline.py` | the whole pipeline | absorb the below extras; become the ONLY publisher |
| `gdocs/tufte_styles.py`, `tufte_cache.py`, `docs_svg.py` | `tufte/styles.py`, `cache.py`, `render/ascii_svg.py` | classic/makarina/crt styles, caches | — |
| `polywhale/crt_render.py` (main-tree copy) | `render/crt_raster.py` + `render/charts.py` | glow/scanlines/vignette, bars, distribution, flow | source colors from `styles.py` (delete local PALETTES); **vendor fonts** (`crt_render.py:20`); make output dir a param (no `/tmp`); **split rendering from Telegram delivery** (`send_crt_photo` → separate `charts.py` stays render-only) |
| `polywhale/generate_pipeline_doc.py` | fold into `pipeline.py`, then **delete** | **per-language syntax highlighting** `_syntax_highlight` (rust/sql/json/toml/sh, `:1007`) | drop `rsvg-convert` (use `ascii_svg`); delete duplicate cyan palette (`:37`); un-hardcode creds/email/project paths (`:29–33`); the 3 inline SVG + EN/RU heading map are *content*, not lib code |
| `polywhale/sentinel_common.py` (journaling) | `tufte/journal.py` (**opt-in append mode**) | tab-per-day append via Docs REST | **add the missing guard**: track char/tab count, auto-spill to `…(cont. N)` **before** the ~1.02M-char/42-tab cap; handle 400; this is the supported version of what was rejected |
| `tufte-illustration` (`render.sh`, `template.html`, `trim.py`) | `render/illustration.py` + `tufte/fonts/` | HTML/CSS component library, 2× render, trim | point headless at **Chro**; **bundle Domine** locally (kill `--virtual-time-budget` network fetch); keep the vision self-check as an optional post-step |
| `pw-tlgrm-source` / `pw-tlgrm-sink` | — (no code) | — | **nothing to migrate**; they inform *content/spec* only |

New MCP tools in `tools.py` (both via the entry_points seam):
- `publish_markdown_tufte(...)` — unchanged signature; add additive `diagrams="auto|svg|crt-raster|illustration"`.
- `render_tufte_graphic(kind, data, style, upload=True)` — render a table/bar/diagram/distribution/illustration to PNG + optional Drive link. Lets **any** client (incl. the PolyWhale Telegram bots) get CRT graphics **without** copying `crt_render.py`.

---

## 4. Skill + registry integration

**Model:** `jmpnop/registry` is a Claude Code **plugin marketplace** (`.claude-plugin/marketplace.json`; per-plugin `version`). A plugin can bundle **both** an MCP server (`.mcp.json`) **and** `skills/` — the official `discord`/`telegram`/`imessage` pattern — which is the *only* way Claude Code expresses "this skill needs these MCP tools" (co-installation; there is no skill→MCP dependency field).

**Plan:**
1. **One skill** `gdocs-tufte/SKILL.md` (H2 sections **Classic** and **CRT (C/A/G)** carrying the existing per-style spec tables), `allowed-tools: mcp__google__publish_markdown_tufte`. Replaces the three loose skills.
2. **Bundle it with the MCP** inside the `google-workspace-mcp` repo as a `plugin/` subtree:
   ```
   google_workspace_mcp/plugin/
     .claude-plugin/plugin.json     # name: gdocs-tufte, version, description
     .mcp.json                      # the workspace MCP server (name: google)
     skills/gdocs-tufte/SKILL.md    # single skill, Classic + CRT sections
   ```
3. **Register** in `registry/.claude-plugin/marketplace.json` via a git source:
   ```json
   { "name": "gdocs-tufte",
     "source": { "source": "github", "repo": "jmpnop/google-workspace-mcp", "path": "plugin" },
     "description": "Publish Tufte-styled Google Docs (Classic + CRT) via the workspace MCP." }
   ```
   → `/plugin install gdocs-tufte@registry` delivers skill **and** MCP atomically.
4. **Server-name collision gotcha:** a `google` server already exists at user level (`~/.claude/.mcp.json`). Keep the bundled server named **`google`** (re-declares localhost:8000) so the `mcp__google__publish_markdown_tufte` prefix stays valid everywhere. (Alternative `google_tufte` namespace only if full portability is wanted — costs a tool-prefix rename.)
5. **Deprecate** `gdocs-tufte-classic` and `gdocs-tufte-crt`: they were never in the registry, so cleanup = delete the three loose `~/.claude/skills/gdocs-tufte*` dirs after the plugin installs. Leave `tufte-illustration` and `gslides-tufte` (separate surfaces) untouched — except `tufte-illustration`'s renderer is *copied* into the plugin lib (the skill can stay standalone or later call `render_tufte_graphic`).

---

## 5. Migration order (each phase independently shippable)

- **Phase 0 — Audit & seam design.** ✅ (this doc; 5-agent audit complete.)
- **Phase 1 — Upstream the seam.** Add the ~7-line `entry_points` scan at `main.py:318`; PR to `taylorwilsdon/google_workspace_mcp`. Land it (or carry as the single fork patch). Gate: an empty test plugin registers a no-op tool.
- **Phase 2 — Scaffold `gdocs-tufte-plugin`.** New package; move core's `tufte_*` + `docs_svg` in as `tufte/{styles,pipeline,cache,render/ascii_svg}`; declare the entry point; import auth/error/docs helpers from core. Delete the fork's in-core Tufte files + the `main.py:241` wiring. Gate: republish one known doc in `classic` + `crt`, pixel-diff vs current (identical).
- **Phase 3 — Port the raster renderer.** `crt_render.py` → `render/crt_raster.py` + `charts.py`; colors from `styles.py`; **vendor fonts**; output dir param; strip Telegram coupling. Unit tests: each palette → near-black bg (luma<15) + phosphor fg.
- **Phase 4 — Collapse the second publisher.** Port `_syntax_highlight` into pipeline phase 4.5; replace `rsvg-convert` with `ascii_svg`; delete duplicate cyan palette; then **delete `generate_pipeline_doc.py`**. Gate: reproduce `PolyWhale Telegram Pipeline` (+ RU) from markdown via `style=crt, diagrams=crt-raster|svg`.
- **Phase 5 — Illustration renderer.** Port `tufte-illustration` → `render/illustration.py`; point at **Chro**; bundle Domine. Gate: render one classic panel headless via Chro.
- **Phase 6 — `render_tufte_graphic` tool + PolyWhale cutover.** Expose the tool; PolyWhale imports the lib / calls the tool; **delete `crt_render.py` copies across all `polywhale/.claude/worktrees/*`**.
- **Phase 7 — Skill + registry.** Ship the `plugin/` bundle; register in `registry`; delete the 3 loose gdocs-tufte skills.
- **Phase 8 — Supported journaling (optional).** `tufte/journal.py` with the char/tab **size guard + auto-rollover** to `(cont. N)` — the correct version of the rejected mechanism, so a growing journal spills *before* the 1.02M/42-tab cap instead of 400-ing.

---

## 6. Decisions & risks

1. **De-fork via upstream seam.** The entry_points hook is designed to be upstream-acceptable (generic plugin mechanism, not Tufte-specific). If upstream declines, it stays as the fork's *single* patch — still a massive reduction from six fork-added files.
2. **Chro is a declared dependency** for the illustration renderer (`/Applications/Chro.app`, v146). SVG + Pillow renderers remain pure-Python and always-available; illustration is the "rich" backend.
3. **Font vendoring is mandatory** — the hardcoded `ghostty-source` JetBrains Mono path and the network Domine fetch both break portability. Bundle both `.ttf`s in `tufte/fonts/`.
4. **One palette source.** All colors live in `styles.py`; the two cyan definitions and `crt_render.PALETTES` are deleted in favor of it.
5. **Journal rollover is now in-scope** (Phase 8) because the plugin owns a *supported* append mode with a guard — but it must **auto-spill within the plugin**, never silently, and log each rollover.
6. **Server-name:** reuse `google` to keep tool prefixes stable.
7. **Backward compat:** `publish_markdown_tufte` signature unchanged; `doc_index.json`/`image_cache.json` reused as-is.
8. **Build-out orchestration:** use **`leashed-swarm`** for any multi-round agent work from here (bounded rounds, supervisor, `Monitor`) — the audit's unleashed agents ran ~55 h.

## 7. Success criteria

- Core `google-workspace-mcp` carries **one** upstreamable line-group of Tufte-related change (the entry_points scan) — ideally zero after upstreaming; **all** Tufte files live in the plugin.
- **One** publisher, **one** style registry, **three** renderers behind one interface, **one** skill, **one** plugin, **one** marketplace entry.
- PolyWhale contains **zero** copies of `crt_render.py` / `generate_pipeline_doc.py`; it imports the lib or calls `render_tufte_graphic`.
- The two existing CRT docs are **reproducible from markdown**; a new CRT doc with tables + diagrams is one tool call.
- Adding a style, chart type, or renderer is a one-file change in the plugin.

---

### Appendix — canonical files & evidence

- **Core (fork-added, to remove):** `gdocs/tufte_tools.py`, `tufte_publisher.py`, `tufte_styles.py`, `tufte_cache.py`, `docs_svg.py`, `docs_git_versioning.py`; wiring at `main.py:241`. Fork merge-base `9631b9e` vs `taylorwilsdon/google_workspace_mcp`.
- **Core infra to reuse:** `auth/service_decorator.py:719` (`require_multiple_services`), `core/utils.py:375` (`handle_http_errors`), `gdocs/docs_helpers.py`/`docs_tables.py`/`docs_markdown.py`/`docs_structure.py`, singleton `core/server.py:57`, seam point `main.py:318`.
- **PolyWhale (main tree):** `agents/crt_render.py` (41 KB; fonts `:20`, PALETTES `:23`, `crt_finalize` `:63`), `agents/generate_pipeline_doc.py` (72 KB; `_syntax_highlight` `:1007`, `_render_svg`/rsvg `:479`, cyan dup `:37`), `agents/sentinel_common.py` (journaling; `DOC_ID` `:19`, tabs `:264`, append `:430`; cap documented in polywhale `CLAUDE.md`, deprecated 2026-06-17). Rust crates `pw_tap/`, `pw_sink/` — no gdocs code.
- **tufte-illustration:** `= ~/.claude/skills/tufte-illustration` (`render.sh`, `template.html`, `trim.py`, `template.png`) = `github.com/jmpnop/tufte-illustration`.
- **Registry:** `jmpnop/registry` marketplace (`.claude-plugin/marketplace.json`); MCP+skills bundling pattern per official `discord`/`telegram` plugins.
- **Caches / dirs:** `~/.google_workspace_mcp/cache/tufte/{doc_index,image_cache}.json`; attachments `~/.workspace-mcp/attachments`.
- **Reference CRT docs:** `PolyWhale Telegram Pipeline` `1O9YiSTmFIyGoci4qGS6deEjyqS_1rVO9H1VZc47xmYc`; RU `1S9MlEoDE2dcLIaVc0GeNdJo2N4r6MrlECQVG7SHUubQ`.
