#!/usr/bin/env python3
"""Emit media/hero.svg. Every number comes from compare.py, the shadow-medic script that scores the challenger model against the trusted model's verdicts and prints the gate's decision, through tools/facts.py.

    python3 tools/render_hero.py --write    regenerate
    python3 tools/render_hero.py --check    exit 1 with a diff if the committed file drifted
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402
import palette as P  # noqa: E402

OUT = os.path.join(P.ROOT, "media", "hero.svg")
W, H = 1200, 524
M = 48


def build():
    rows, f = facts.load()
    held = [r for r in rows if r["split"] == "holdout"]
    out = [P.svg_open(W, H, "Shadow deployment for LLM workflows: scoreboard and the four rungs")]
    inner = W - 2 * M
    out.append(P.t(M, 54, "SHADOW DEPLOYMENT FOR LLM WORKFLOWS", 23, P.MUTED, spacing=2, inner=inner))
    out.append(P.t(M, 112, "A new model earns production", 44, P.INK, bold=True, inner=inner))
    out.append(P.t(M, 164, "in the shadow of the old one", 44, P.INK, bold=True, inner=inner))
    out.append(P.t(M, 212, "Same incidents, same rulebook, no tools. A sequential test says promote,", 25, P.MUTED, inner=inner))
    out.append(P.t(M, 244, "keep shadowing or reject, one job family at a time.", 25, P.MUTED, inner=inner))

    top, ch, gap = 270, 124, 24
    widths = [300, (inner - 300 - 2 * gap) // 2, (inner - 300 - 2 * gap) // 2]
    cards = [
        (str(len(held)), ["held-out incidents"], None),
    ]
    for fam in facts.FAMILIES:
        d = f[fam]
        cards.append((f"{d['agreements']} / {d['scored']}",
                      [f"{fam} agreements", facts.verdict_word(d["decision"])], d["decision"]))
    x = M
    for (big, cap, dec), w in zip(cards, widths):
        out.append(P.rect(x, top, w, ch, P.PANEL, P.EDGE))
        # one thin rule along the top edge carries the verdict color; nothing else on the card is colored
        out.append(P.rect(x, top, w, 4, facts.decision_color(dec, P) if dec else P.MUTED))
        out.append(P.t(x + 22, top + 54, big, 40, P.INK, bold=True, inner=w - 44))
        for i, line in enumerate(cap):
            out.append(P.t(x + 22, top + 86 + i * 30, line, 24, P.MUTED, inner=w - 44))
        x += w + gap

    labels = ["1 shadow, logs handed over", "2 read-only tools", "3 live diagnosis", "4 the switch"]
    pad, pgap, py, ph = 16, 8, 424, 44
    x = M
    for i, lab in enumerate(labels):
        w = int(P.fit(lab, 23, 10_000)) + 2 * pad
        if i == 0:  # the rung that has run: an accent outline, no fill
            out.append(P.rect(x, py, w, ph, P.PANEL, P.ACCENT, sw=3))
            out.append(P.t(x + pad, py + 30, lab, 23, P.INK, bold=True, inner=w - 2 * pad + 40))
        else:
            out.append(P.rect(x, py, w, ph, "none", P.EDGE))
            out.append(P.t(x + pad, py + 30, lab, 23, P.MUTED, inner=w - 2 * pad + 40))
        x += w + pgap
    if x - pgap > W - M:
        raise ValueError("pill row overflows the hero")
    # shadow-medic/compare.py scoreboard prints agreement and the sequential-test verdict for one job family; ops is scheduled automation, render is avatar video renders.
    out.append(P.t(M, 508, "python3 shadow-medic/compare.py scoreboard --family ops | --family render", 23, P.MUTED, mono=True, inner=inner))
    out.append("</svg>\n")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(P.run(sys.argv[1:], OUT, build))
