#!/usr/bin/env python3
"""Emit media/system-map.svg. Counts and the two SPRT increments come from compare.py through tools/facts.py.

    python3 tools/render_map.py --write | --check

The medic is the trusted Claude agent that diagnoses failed scheduled jobs; the challenger is the candidate model tested against it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402
import palette as P  # noqa: E402

OUT = os.path.join(P.ROOT, "media", "system-map.svg")
W = 1200
X0, X1 = 44, 1156
GAP = 20


def wrap(text, size, inner):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        try:
            P.fit(trial, size, inner)
            cur = trial
        except ValueError:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def card_h(c, w):
    lines = wrap(c["detail"], 24, w - 40)
    return 20 + 34 + 30 * len(lines) + (34 if c.get("foot") else 0) + 14, lines


def draw_cards(out, y, cards, ncols, widths=None):
    even = (X1 - X0 - GAP * (ncols - 1)) // ncols
    widths = widths or [even] * ncols
    rows = [cards[i:i + ncols] for i in range(0, len(cards), ncols)]
    for row in rows:
        hh = max(card_h(c, widths[i])[0] for i, c in enumerate(row))
        x = X0
        for i, c in enumerate(row):
            w = widths[i]
            out.append(P.rect(x, y, w, hh, P.PANEL, P.EDGE))
            if c.get("accent"):
                out.append(f'<rect x="{x + 8}" y="{y}" width="{w - 16}" height="5" fill="{P.ACCENT}"/>')
            out.append(P.t(x + 20, y + 40, c["title"], 26, P.INK, bold=True, inner=w - 40))
            for j, ln in enumerate(card_h(c, w)[1]):
                out.append(P.t(x + 20, y + 74 + j * 30, ln, 24, P.INK, inner=w - 40))
            if c.get("foot"):
                out.append(P.t(x + 20, y + hh - 18, c["foot"], 23, P.MUTED, mono=True, inner=w - 40))
            x += w + GAP
        y += hh + GAP
    return y


def build():
    rows, f = facts.load()
    held = [r for r in rows if r["split"] == "holdout"]
    scored = sum(1 for r in held if r["result"] != "PENDING")
    pending = len(held) - scored
    up, down, bound = facts.increments()

    sections = [
        ("01", "THE SEAM", "one env flag, nowhere else", 1, [
            {"title": "One model call",
             "detail": "The trusted model's diagnosis runs through a single call behind an env flag. The challenger plugs in there, nowhere else.",
             "foot": "run-shadow.sh"}]),
        ("02", "THE LOOP", "free answer keys, same question", 3, [
            {"title": "Ledger", "detail": "Every verdict the trusted model logs becomes an answer key, free.", "foot": "harvest.py"},
            {"title": "Frozen incident", "detail": "Logs from before the incident, the rulebook word for word, no tools.", "foot": "cases/<id>/"},
            {"title": "Shadow run and compare", "detail": "The challenger answers the same question. compare.py scores agreement.", "foot": "compare.py"}]),
        ("03", "THE GATE", "tuning data never counts", 2, [
            {"title": "Holdout only", "detail": "Incidents used while tuning are marked dev and never reach the gate.", "foot": "dev-set.txt"},
            {"title": "Sequential test",
             "detail": f"{up:+.2f} per agreement, {down:+.2f} per miss. Promote at {bound:+.2f}, reject at {-bound:+.2f}.",
             "foot": "compare.py scoreboard"}]),
        ("04", "THE LADDER", "four rungs, one per trust level", 2, [
            {"title": "1 Shadow", "detail": "Logs handed over, no tools. Live now.", "accent": True},
            {"title": "2 Read-only tools", "detail": "The challenger reads evidence itself, still cannot act."},
            {"title": "3 Live diagnosis", "detail": "It diagnoses in production while the trusted model keeps the keys."},
            {"title": "4 The switch", "detail": "One env var per job family that has cleared the gate."}]),
    ]

    body = []
    y = 200
    for num, label, note, ncols, cards in sections:
        body.append(P.t(X0, y + 24, f"{num}  {label}", 24, P.INK, bold=True, spacing=1, inner=X1 - X0))
        body.append(P.t(X0 + 260, y + 24, note, 23, P.MUTED, inner=X1 - X0 - 260))
        body.append(f'<line x1="{X0}" y1="{y + 40}" x2="{X1}" y2="{y + 40}" stroke="{P.EDGE}" stroke-width="1.5"/>')
        y = draw_cards(body, y + 56, cards, ncols, [300, 360, 412] if ncols == 3 else None) + 10
    H = y + 8
    out = [P.svg_open(W, H, "System map: how a challenger earns the switch")]
    out.append(f'<rect x="0" y="0" width="10" height="{H}" fill="{P.ACCENT}"/>')
    out.append(P.t(X0, 56, "SYSTEM MAP", 23, P.MUTED, spacing=2, inner=300))
    out.append(P.t(X0, 116, "How a challenger earns the switch", 44, P.INK, bold=True, inner=1100))
    out.append(P.t(X0, 160, "One seam, one loop, one gate, four rungs", 25, P.MUTED, inner=1100))
    stat = f"{scored} scored · {pending} pending"
    out.append(P.rect(756, 28, 400, 52, P.PANEL, P.EDGE))
    out.append(P.t(956, 62, stat, 24, P.INK, anchor="middle", inner=360))
    out.extend(body)
    out.append("</svg>\n")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(P.run(sys.argv[1:], OUT, build))
