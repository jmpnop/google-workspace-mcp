"""
Tufte Style Definitions

Dataclass-based style presets for the Tufte publishing pipeline.
Classic (light) and CRT (dark, with Cyan/Amber/Green color variants).
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class TufteStyle:
    """Complete Tufte formatting specification."""

    name: str

    # Colors (rgbColor dicts for the Docs API)
    ink: Dict[str, float]            # Primary text
    h3_color: Dict[str, float]       # H3 text
    h4_color: Dict[str, float]       # H4 text
    code_bg: Dict[str, float]        # Code block background shading
    background: Optional[Dict[str, float]] = None  # Doc background (None = white)

    # Page layout
    page_width_pt: int = 792
    page_height_pt: int = 612
    margin_top_pt: int = 54
    margin_bottom_pt: int = 54
    margin_left_pt: int = 54
    margin_right_pt: int = 54

    # Typography sizes
    title_size: int = 24
    h1_size: int = 18
    h2_size: int = 14
    h3_size: int = 12
    h4_size: int = 12
    body_size: int = 12
    table_size: int = 10
    code_size: int = 9

    # Typography weight/style
    title_bold: bool = False
    h1_bold: bool = False
    h2_bold: bool = True
    h3_bold: bool = False
    h4_italic: bool = True

    # Spacing
    line_spacing: int = 115          # Percentage
    space_below_pt: int = 3          # Universal
    h2_space_above_pt: int = 24
    h3_space_above_pt: int = 0
    h4_space_above_pt: int = 0

    # Table borders
    table_border_color: Dict[str, float] = field(
        default_factory=lambda: {"red": 0.7, "green": 0.7, "blue": 0.7}
    )
    table_border_width: float = 0.5

    # Font
    font_family: str = "JetBrains Mono"
    font_weight: int = 400


# ---------------------------------------------------------------------------
# Classic preset — white bg, near-black ink
# ---------------------------------------------------------------------------

TUFTE_CLASSIC = TufteStyle(
    name="classic",
    ink={"red": 0.102, "green": 0.102, "blue": 0.102},           # #1A1A1A
    h3_color={"red": 0.263, "green": 0.263, "blue": 0.263},
    h4_color={"red": 0.4, "green": 0.4, "blue": 0.4},
    code_bg={"red": 0.95, "green": 0.95, "blue": 0.95},          # Light gray
    background=None,                                                # White (default)
)

# ---------------------------------------------------------------------------
# CRT presets — near-black bg, phosphor-colored text
# ---------------------------------------------------------------------------

_CRT_NEAR_BLACK = {"red": 0.004, "green": 0.004, "blue": 0.004}  # #010101
_CRT_GHOST_CYAN = {"red": 0.004, "green": 0.07, "blue": 0.07}
_CRT_GHOST_AMBER = {"red": 0.07, "green": 0.042, "blue": 0.004}
_CRT_GHOST_GREEN = {"red": 0.004, "green": 0.07, "blue": 0.004}

_CRT_COMMON = dict(
    page_width_pt=820,
    page_height_pt=1100,
    margin_top_pt=18,
    margin_bottom_pt=18,
    margin_left_pt=0,
    margin_right_pt=0,
    title_size=28,
    h1_size=22,
    h2_size=16,
    h3_size=13,
    h4_size=12,
    body_size=11,
    table_size=10,
    code_size=9,
    title_bold=True,
    h1_bold=True,
    h2_bold=True,
    h3_bold=False,
    h4_italic=True,
    h2_space_above_pt=18,
    h3_space_above_pt=12,
    table_border_width=0,
    font_family="JetBrains Mono",
    font_weight=400,
    background=_CRT_NEAR_BLACK,
)

TUFTE_CRT_CYAN = TufteStyle(
    name="crt-c",
    ink={"red": 0.0, "green": 0.8, "blue": 0.8},           # NORMAL (body)
    h3_color={"red": 0.0, "green": 0.55, "blue": 0.55},    # DIM
    h4_color={"red": 0.0, "green": 0.314, "blue": 0.314},  # FAINT
    code_bg=_CRT_GHOST_CYAN,
    table_border_color={"red": 0.0, "green": 0.314, "blue": 0.314},
    **_CRT_COMMON,
)
# Title/H1 use BRIGHT, stored separately
_CRT_BRIGHT_CYAN = {"red": 0.0, "green": 1.0, "blue": 1.0}

TUFTE_CRT_AMBER = TufteStyle(
    name="crt-a",
    ink={"red": 0.8, "green": 0.48, "blue": 0.0},
    h3_color={"red": 0.55, "green": 0.33, "blue": 0.0},
    h4_color={"red": 0.314, "green": 0.188, "blue": 0.0},
    code_bg=_CRT_GHOST_AMBER,
    table_border_color={"red": 0.314, "green": 0.188, "blue": 0.0},
    **_CRT_COMMON,
)
_CRT_BRIGHT_AMBER = {"red": 1.0, "green": 0.6, "blue": 0.0}

TUFTE_CRT_GREEN = TufteStyle(
    name="crt-g",
    ink={"red": 0.0, "green": 0.8, "blue": 0.0},
    h3_color={"red": 0.0, "green": 0.55, "blue": 0.0},
    h4_color={"red": 0.0, "green": 0.314, "blue": 0.0},
    code_bg=_CRT_GHOST_GREEN,
    table_border_color={"red": 0.0, "green": 0.314, "blue": 0.0},
    **_CRT_COMMON,
)
_CRT_BRIGHT_GREEN = {"red": 0.0, "green": 1.0, "blue": 0.0}

# Map CRT variants to their BRIGHT color (used for Title/H1)
CRT_BRIGHT = {
    "crt-c": _CRT_BRIGHT_CYAN,
    "crt-a": _CRT_BRIGHT_AMBER,
    "crt-g": _CRT_BRIGHT_GREEN,
}

# Lookup table: style name -> TufteStyle
STYLES = {
    "classic": TUFTE_CLASSIC,
    "crt": TUFTE_CRT_CYAN,      # Default CRT = cyan
    "crt-c": TUFTE_CRT_CYAN,
    "crt-a": TUFTE_CRT_AMBER,
    "crt-g": TUFTE_CRT_GREEN,
}


def get_style(name: str) -> TufteStyle:
    """Resolve a style name to a TufteStyle instance."""
    key = name.lower().strip()
    if key not in STYLES:
        raise ValueError(f"Unknown Tufte style '{name}'. Choose from: {list(STYLES.keys())}")
    return STYLES[key]


def get_title_color(style: TufteStyle) -> Dict[str, float]:
    """Return the title/H1 color for a style.

    Classic uses the same INK as body text.
    CRT variants use a brighter phosphor for Title/H1.
    """
    return CRT_BRIGHT.get(style.name, style.ink)


# ---------------------------------------------------------------------------
# Request builders (parameterized by style)
# ---------------------------------------------------------------------------

def fmt_text(
    start: int,
    end: int,
    style: TufteStyle,
    font_size: Optional[int] = None,
    bold: Optional[bool] = None,
    italic: Optional[bool] = None,
    fg_color: Optional[Dict[str, float]] = None,
    bg_color: Optional[Dict[str, float]] = None,
) -> dict:
    """Build an updateTextStyle request."""
    ts = {}
    fields = []

    ts["weightedFontFamily"] = {"fontFamily": style.font_family, "weight": style.font_weight}
    fields.append("weightedFontFamily")

    if font_size is not None:
        ts["fontSize"] = {"magnitude": font_size, "unit": "PT"}
        fields.append("fontSize")

    if bold is not None:
        ts["bold"] = bold
        fields.append("bold")

    if italic is not None:
        ts["italic"] = italic
        fields.append("italic")

    color = fg_color if fg_color is not None else style.ink
    ts["foregroundColor"] = {"color": {"rgbColor": color}}
    fields.append("foregroundColor")

    if bg_color is not None:
        ts["backgroundColor"] = {"color": {"rgbColor": bg_color}}
        fields.append("backgroundColor")

    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": ts,
            "fields": ",".join(fields),
        }
    }


def fmt_heading(
    start: int,
    end: int,
    level: int,
    space_above: int = 0,
    space_below: int = 3,
) -> dict:
    """Build an updateParagraphStyle request for a heading."""
    if level == -1:
        named = "TITLE"
    elif level == 0:
        named = "NORMAL_TEXT"
    else:
        named = f"HEADING_{level}"

    ps = {"namedStyleType": named}
    fields = ["namedStyleType"]

    if space_above:
        ps["spaceAbove"] = {"magnitude": space_above, "unit": "PT"}
        fields.append("spaceAbove")
    if space_below:
        ps["spaceBelow"] = {"magnitude": space_below, "unit": "PT"}
        fields.append("spaceBelow")

    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "paragraphStyle": ps,
            "fields": ",".join(fields),
        }
    }
