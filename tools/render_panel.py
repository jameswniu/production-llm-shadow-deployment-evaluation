#!/usr/bin/env python3
"""Emit media/agreement-panel.svg from compare.py's own numbers (through tools/facts.py).

    python3 tools/render_panel.py --write | --check | --print-facts

The medic is the trusted model whose class is the answer key, the challenger is the candidate model, MECHANICAL means a rerun or a close by rule, and JUDGMENT means a person has to look.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402
import palette as P  # noqa: E402

OUT = os.path.join(P.ROOT, "media", "agreement-panel.svg")
W, H = 1200, 560
TINT = ' fill-opacity="0.25"'


def miss_box(x, y, w, h, solid):
    """The two miss directions share one hue: a solid box for one, an outlined box for the other."""
    if solid:
        return P.rect(x, y, w, h, P.MUTED)
    return P.rect(x + 1, y + 1, max(w - 2, 0), h - 2, P.PANEL, P.MUTED)


def build():
    _, f = facts.load()
    o = [P.svg_open(W, H, "Agreement with the trusted model on held-out incidents, and the misses by direction")]
    # ---- left chart
    o.append(P.t(40, 58, "Agreement on held-out incidents", 26, P.INK, bold=True, inner=610))
    px0, pw = 140, 500
    def X(p):
        return round(px0 + pw * p, 1)
    top, bot = 190, 392
    # reference lines; the 92 label sits in the upper row, the 80 label in the lower row so neither crosses a line
    o.append(P.line(X(.92), top - 40, X(.92), bot, P.MUTED, dash="8 6"))
    o.append(P.line(X(.80), top - 6, X(.80), bot, P.MUTED, dash="8 6"))
    o.append(P.t(X(.92) - 8, top - 62 + 22, "92% worth promoting", 23, P.MUTED, anchor="end", inner=X(.92) - 40))
    o.append(P.t(X(.80) - 8, top - 6 + 2 - 8 + 8, "80% not good enough", 23, P.MUTED, anchor="end", inner=X(.80) - 40))
    for i, fam in enumerate(facts.FAMILIES):
        d = f[fam]
        ty = 236 + i * 90
        by = ty + 12
        col = facts.decision_color(d["decision"], P)
        o.append(P.t(40, ty + 36, fam, 24, P.INK, bold=True))
        # the verdict color as an outline with a faint tint, never a solid fill
        o.append(P.rect(px0, by, round(pw * d["rate"], 1), 40, col, col, extra=TINT))
        cy = by + 20
        lo, hi = X(d["wilson_low"]), X(d["wilson_high"])
        o.append(P.line(lo, cy, hi, cy, P.INK, sw=3))
        o.append(P.line(lo, cy - 11, lo, cy + 11, P.INK, sw=3))
        o.append(P.line(hi, cy - 11, hi, cy + 11, P.INK, sw=3))
        o.append(P.t(px0, ty + 2, f"{d['agreements']} / {d['scored']} · {round(d['rate'] * 100)}%", 24, P.INK, bold=True, inner=300))
        o.append(P.t(px0 + 190, ty + 2, facts.verdict_word(d["decision"]), 24, col, inner=200))
    o.append(P.line(px0, bot, px0 + pw, bot))
    for p in (0, .5, 1):
        o.append(P.t(X(p), bot + 32, f"{round(p * 100)}%", 23, P.MUTED, anchor="middle"))
    o.append(P.t(40, 470, "Whisker: Wilson 95% interval", 23, P.MUTED, inner=610))
    # ---- right chart
    rx0, rw = 700, 460
    o.append(P.t(rx0, 58, "The misses, by direction", 26, P.INK, bold=True, inner=rw))
    mx = max(d["misses"] for d in f.values())
    unit = rw / mx if mx else 0
    for i, fam in enumerate(facts.FAMILIES):
        d = f[fam]
        a, b = d["medic_judgment_challenger_mechanical"], d["medic_mechanical_challenger_judgment"]
        ty = 156 + i * 100
        o.append(P.t(rx0, ty, f"{fam} · {d['misses']} misses", 24, P.INK, bold=True, inner=rw))
        x = rx0
        for n, solid in ((a, True), (b, False)):
            if not mx:
                break
            w = round(n * unit, 1)
            o.append(miss_box(x, ty + 14, w, 44, solid))
            o.append(P.t(round(x + w / 2, 1), ty + 45, str(n), 24, P.GROUND if solid else P.INK, bold=True, anchor="middle"))
            x += w
    ly = 380
    for j, (solid, l1, l2) in enumerate(((True, "medic JUDGMENT,", "challenger MECHANICAL"), (False, "medic MECHANICAL,", "challenger JUDGMENT"))):
        yy = ly + j * 66
        o.append(miss_box(rx0, yy - 20, 26, 26, solid))
        o.append(P.t(rx0 + 40, yy, l1, 23, P.INK, inner=rw - 40))
        o.append(P.t(rx0 + 40, yy + 28, l2, 23, P.INK, inner=rw - 40))
    o.append(P.t(40, 530, "python3 tools/render_panel.py --check", 23, P.MUTED, mono=True, inner=1100))
    o.append("</svg>\n")
    return "\n".join(o)


def print_facts():
    _, f = facts.load()
    out = {}
    for fam in facts.FAMILIES:
        d = dict(f[fam])
        d["wilson_low"] = round(d["wilson_low"], 4)
        d["wilson_high"] = round(d["wilson_high"], 4)
        d["rate"] = round(d["rate"], 4)
        out[fam] = d
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--print-facts"]:
        sys.exit(print_facts())
    sys.exit(P.run(sys.argv[1:], OUT, build))
