"""Per-language syntax highlighting for Tufte code blocks.

Pure, style-agnostic token spanning ported from polywhale's generate_pipeline_doc
`_syntax_highlight` (rust/sql/json/toml/sh). Returns character spans + a role so
the publisher can emit updateTextStyle requests in the active style's palette —
no hardcoded cyan, no document-index coupling (that lives in the pipeline).

highlight_spans(line, lang) -> list[Span], where Span = (start, end, role) and
role is "comment" | "keyword". The publisher maps role -> color:
  comment -> style FAINT (+italic), keyword -> style BRIGHT.
"""

import re
from typing import List, Tuple

Span = Tuple[int, int, str]  # (start, end, role)

_RUST_KW = re.compile(
    r"\b(pub|trait|fn|impl|struct|let|mut|async|await|use|mod|crate|enum|dyn|"
    r"const|static|usize|u8|u16|u32|u64|i32|i64|f32|f64|self|Self|return|where|"
    r"for|in|if|else|match|true|false)\b"
)
_SQL_KW = re.compile(
    r"\b(SELECT|FROM|WHERE|INSERT|CREATE|TABLE|VIEW|INTO|GROUP BY|ORDER BY|"
    r"UNIQUE|PRIMARY KEY|INTEGER|TEXT|REAL|COUNT|SUM|DISTINCT|LIMIT|HAVING|"
    r"PRAGMA|DROP|ALTER|DELETE|UPDATE|FOREIGN|REFERENCES|NULL|VALUES|NOT)\b"
)
_COMMENT = re.compile(r"^(#(?!!)\s|//\s|--\s)")
_JSON_KEY = re.compile(r'"([^"]+)"\s*:')
_TOML_SECTION = re.compile(r"\[{1,2}[^\]]+\]{1,2}")
_TOML_KEY = re.compile(r"(\w[\w-]*)\s*=")
_SH_VAR = re.compile(r"\$\{?\w+\}?")

_NBSP = " "
_PROG_LANGS = {"sh", "rust", "sql", "toml", "json"}


def highlight_spans(line: str, lang: str = "") -> List[Span]:
    """Return [(start, end, role)] spans for one code line in language `lang`.

    Offsets are relative to `line`. Untagged blocks (lang="") get no keyword
    coloring — they're CLI help / pseudocode / diagrams.
    """
    lang = (lang or "").lower()
    stripped = line.lstrip(_NBSP)
    indent = len(line) - len(stripped)

    # Whole-line comments (known languages only)
    if lang in _PROG_LANGS and _COMMENT.match(stripped):
        return [(0, len(line), "comment")]

    if not lang:
        return []

    spans: List[Span] = []
    if lang == "json":
        for m in _JSON_KEY.finditer(line):
            spans.append((m.start(), m.end() - 1, "keyword"))  # exclude colon
    elif lang == "toml":
        m = _TOML_SECTION.match(stripped)
        if m:
            spans.append((indent + m.start(), indent + m.end(), "keyword"))
        m = _TOML_KEY.match(stripped)
        if m:
            spans.append((indent + m.start(1), indent + m.end(1), "keyword"))
    elif lang == "rust":
        spans += [(m.start(), m.end(), "keyword") for m in _RUST_KW.finditer(line)]
    elif lang == "sql":
        spans += [(m.start(), m.end(), "keyword") for m in _SQL_KW.finditer(line)]
    elif lang == "sh":
        spans += [(m.start(), m.end(), "keyword") for m in _SH_VAR.finditer(line)]
    return spans
