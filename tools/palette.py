"""Shared colors, fonts, SVG helpers and the text-fit guard for every figure generator."""
import difflib
import html
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GROUND = "#041c1c"
PANEL = "#0b2f2f"
EDGE = "#B8860B"
INK = "#ffe6cb"
MUTED = "#C7A96B"
ACCENT = "#FFBF00"
GOOD = "#34d399"
BAD = "#d14a4a"
FONT_SANS = "-apple-system, Segoe UI, Helvetica, Arial, sans-serif"
FONT_MONO = "SF Mono, Menlo, Consolas, monospace"
FLOOR = 23


def fit(text, size, box_inner_width, bold=False, spacing=0):
    """Raise ValueError naming the string when its estimated width exceeds the box."""
    if size < FLOOR:
        raise ValueError(f"font {size} below the {FLOOR} floor for {text!r}")
    est = len(text) * size * (0.62 if bold else 0.58) + max(len(text) - 1, 0) * spacing
    if est > box_inner_width:
        raise ValueError(f"text does not fit: {text!r} needs {est:.0f} of {box_inner_width:.0f}")
    return est


def esc(s):
    return html.escape(s, quote=True)


def t(x, y, s, size, fill=INK, bold=False, mono=False, anchor=None, spacing=None, inner=None, extra=""):
    """One text element. When `inner` (box inner width) is given, the fit guard runs."""
    if inner is not None:
        fit(s, size, inner, bold, spacing or 0)
    a = f' text-anchor="{anchor}"' if anchor else ""
    sp = f' letter-spacing="{spacing}"' if spacing else ""
    w = ' font-weight="700"' if bold else ""
    fam = FONT_MONO if mono else FONT_SANS
    return (f'<text x="{x}" y="{y}" font-family="{esc(fam)}" font-size="{size}" fill="{fill}"{w}{a}{sp}{extra}>'
            f'{esc(s)}</text>')


def rect(x, y, w, h, fill="none", stroke=None, sw=1.5, rx=8, dash=None):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}{d}/>'


def svg_open(w, h, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" '
            f'aria-label="{esc(label)}">\n<rect width="{w}" height="{h}" rx="12" fill="{GROUND}"/>')


def run(argv, out_path, build):
    """Shared --write / --check driver. `build()` returns the file text."""
    mode = argv[0] if argv else ""
    if mode not in ("--write", "--check"):
        print(f"usage: {sys.argv[0]} --write | --check", file=sys.stderr)
        return 64
    new = build()
    rel = os.path.relpath(out_path, ROOT)
    if mode == "--write":
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            f.write(new)
        print(f"wrote {rel}")
        return 0
    try:
        old = open(out_path).read()
    except FileNotFoundError:
        old = ""
    if old == new:
        print(f"ok {rel}")
        return 0
    sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f"a/{rel}", f"b/{rel}"))
    print(f"\ndrift: {rel} differs from its generator")
    return 1
