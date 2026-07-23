"""Tufte Classic illustration renderer — HTML/CSS → headless Chro → trimmed PNG.

Ported from the tufte-illustration skill (render.sh + trim.py). Authors a
self-contained HTML page (warm paper, Domine serif, garnet/gold accents),
screenshots it at 2x via the user's Chro (Chromium) build, and trims trailing
paper so the image hugs its content.

Chro is a declared dependency (the editorial/classic renderer). The lightweight
SVG and Pillow-CRT renderers cover the case where Chro is unavailable.

Two capture backends: CDP (default, `render_html_png_cdp`) drives Chro over the
DevTools Protocol (`Page.captureScreenshot`) and is robust on the local Chro
build, whose code-sign clone (`code_sign_clone_manager`) breaks CLI
`--screenshot`; the CLI path (`render_html_png(prefer="cli")`) works on stock
Chromium/CI. `render_html_png` tries CDP first and falls back to CLI.
"""

import base64
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from PIL import Image

# Declared browser dependency: the user's Chro build, then common fallbacks.
_CHRO_CANDIDATES = [
    "/Applications/Chro.app/Contents/MacOS/Chromium",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
_PAPER = "FBFAF7FF"          # warm Tufte-Classic paper (matches template)
_DEFAULT_WIDTH = 1140
_TRIM_MARGIN = 80            # px kept past last content (2x scale)
_TRIM_TOL = 10

_TEMPLATE = Path(__file__).with_name("illustration_template.html")


def chro_binary() -> str:
    """Return the Chro/Chromium executable, or raise if none is installed."""
    override = os.getenv("TUFTE_CHRO_BIN")
    cands = ([override] if override else []) + _CHRO_CANDIDATES
    for c in cands:
        if c and Path(c).is_file():
            return c
    raise RuntimeError(
        "Chro/Chromium not found for the illustration renderer. Install Chro at "
        "/Applications/Chro.app or set TUFTE_CHRO_BIN."
    )


def load_template() -> str:
    """The blank Tufte-Classic HTML template (design system + Domine link)."""
    return _TEMPLATE.read_text(encoding="utf-8")


def _trim(path: str) -> tuple:
    """Crop trailing bottom/right paper to a uniform margin (port of trim.py)."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = px[3, 3]

    def near(p):
        return all(abs(p[i] - bg[i]) <= _TRIM_TOL for i in range(3))

    last_y = 0
    for y in range(h - 1, -1, -1):
        if any(not near(px[x, y]) for x in range(0, w, 4)):
            last_y = y
            break
    last_x = 0
    for x in range(w - 1, -1, -1):
        if any(not near(px[x, y]) for y in range(0, h, 4)):
            last_x = x
            break
    new_w, new_h = min(w, last_x + _TRIM_MARGIN), min(h, last_y + _TRIM_MARGIN)
    im.crop((0, 0, new_w, new_h)).save(path)
    return new_w, new_h


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def render_html_png_cdp(html: str, width: int = _DEFAULT_WIDTH, out_path: str = None,
                        trim: bool = True, timeout: int = 25) -> str:
    """Render HTML to a 2x PNG via Chro over the DevTools Protocol.

    This is the robust path on the local Chro build (whose code-sign clone
    breaks CLI --screenshot). Launches headless Chro with remote debugging,
    drives Emulation.setDeviceMetricsOverride (2x) + Page.captureScreenshot.
    Requires `websocket-client`.
    """
    from websocket import create_connection  # lazy: only the CDP path needs it

    binary = chro_binary()
    ts = int(time.time())
    out_path = out_path or os.path.join(tempfile.gettempdir(), f"tufte_illus_{ts}.png")
    port = _free_port()
    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "page.html")
        Path(html_path).write_text(html, encoding="utf-8")
        proc = subprocess.Popen(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-first-run", "--no-default-browser-check",
             "--hide-scrollbars", f"--remote-debugging-port={port}",
             "--remote-allow-origins=*",
             f"--user-data-dir={os.path.join(td, 'prof')}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            ws_url = None
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data = urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json", timeout=2
                    ).read()
                    for t in json.loads(data):
                        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                            ws_url = t["webSocketDebuggerUrl"]
                            break
                    if ws_url:
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            if not ws_url:
                raise RuntimeError("Chro CDP endpoint not reachable")

            ws = create_connection(ws_url, timeout=timeout, max_size=None)
            _i = [0]

            def cmd(method, params=None):
                _i[0] += 1
                mid = _i[0]
                ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == mid:
                        return msg.get("result", {})

            cmd("Page.enable")
            cmd("Emulation.setDeviceMetricsOverride",
                {"width": width, "height": 1600, "deviceScaleFactor": 2, "mobile": False})
            cmd("Page.navigate", {"url": f"file://{html_path}"})
            time.sleep(4)  # let layout + the Domine webfont settle
            shot = cmd("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            ws.close()
            Path(out_path).write_bytes(base64.b64decode(shot["data"]))
        finally:
            proc.kill()
            proc.wait()
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise RuntimeError("Chro CDP produced no screenshot")
    if trim:
        _trim(out_path)
    return out_path


def render_html_png(html: str, width: int = _DEFAULT_WIDTH, out_path: str = None,
                    trim: bool = True, timeout: int = 25, prefer: str = "cdp") -> str:
    """Render a full HTML string to a trimmed 2x PNG via headless Chro.

    prefer="cdp" (default) uses the DevTools-Protocol path (robust on the local
    Chro code-sign-clone build); "cli" uses --screenshot (stock Chromium/CI).
    Falls back to the other path on failure.

    Args:
        html: complete HTML document (use load_template() as a base).
        width: logical canvas width (px); rendered at 2x device scale.
        out_path: destination PNG; default a temp file.
        trim: crop trailing paper to a uniform margin.
    Returns the PNG path.
    """
    if prefer == "cdp":
        try:
            return render_html_png_cdp(html, width, out_path, trim, timeout)
        except Exception:
            pass  # fall through to CLI
    binary = chro_binary()
    ts = int(time.time())
    out_path = out_path or os.path.join(tempfile.gettempdir(), f"tufte_illus_{ts}.png")
    if os.path.exists(out_path):
        os.remove(out_path)
    with tempfile.TemporaryDirectory() as td:
        html_path = os.path.join(td, "page.html")
        Path(html_path).write_text(html, encoding="utf-8")
        prof = os.path.join(td, "prof")
        cmd = [
            binary, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--no-sandbox", "--no-first-run", "--no-default-browser-check",
            "--disable-background-networking", "--disable-extensions",
            "--force-device-scale-factor=2", f"--window-size={width},1600",
            "--virtual-time-budget=4000",           # let the Domine webfont load
            f"--default-background-color={_PAPER}",
            f"--user-data-dir={prof}",
            f"--screenshot={out_path}", f"file://{html_path}",
        ]
        # Headless Chro writes the screenshot but often does not exit cleanly
        # (the original render.sh hard-kills it after ~12s). So we time-box the
        # process, kill it, and judge success by whether the PNG was written.
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
        raise RuntimeError("Chro produced no screenshot (headless render failed)")
    if trim:
        _trim(out_path)
    return out_path
