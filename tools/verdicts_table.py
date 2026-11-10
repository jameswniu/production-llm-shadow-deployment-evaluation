#!/usr/bin/env python3
"""Emit docs/verdicts.md, one row per incident, with a per-family summary computed with the same scoring math as compare.py, the script that scores the challenger (GLM-5.3) against the medic (the trusted Claude agent that classed each failed job first) and prints whether the gate says promote, keep shadowing or reject.

    python3 tools/verdicts_table.py --write | --check
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import facts  # noqa: E402
import palette as P  # noqa: E402

OUT = os.path.join(P.ROOT, "docs", "verdicts.md")


def build():
    rows, f = facts.load()
    n = len(rows)
    L = [f"# Every verdict, all {n} incidents", ""]
    L.append("This table checks, incident by incident, whether the challenger (GLM-5.3, given the same logs) classes a failed scheduled job the way the medic (the trusted Claude agent) did, so a reader can count the matches and misses behind every number on the main page.")
    L.append("")
    L.append("Medic class is the trusted model's call, Challenger class is the candidate's, Stage is the letter of the scheduled job that failed (D, E and F are avatar video renders, the render family; the rest are automation, the ops family), Split says whether the incident was held out of tuning, and Logs says whether its logs ship or stay private with only these fields and a hash.")
    L.append("")
    L.append("Each row is one frozen incident: the class the trusted model logged, the class the challenger gave "
             "from the same logs, and whether the two agree. A withheld incident ships only these fields plus a "
             "hash of its private original, never its logs.")
    L.append("")
    L.append("| Incident | Family | Stage | Split | Medic class | Challenger class | Result | Logs |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["family"], r["id"])):
        L.append(f"| {r['id']} | {r['family']} | {r['stage']} | {r['split']} | {r['medic']} | "
                 f"{r['challenger'] or '-'} | {r['result']} | {'shipped' if r['shipped'] else 'withheld'} |")
    L.append("")
    L.append("## Summary, holdout only")
    L.append("")
    L.append("The gate reads the holdout split, so these match the output of `compare.py scoreboard`, the command that prints agreement and the sequential-test verdict per family, to the digit.")
    L.append("")
    L.append("| Family | Scored | Matched | Missed | Pending | SPRT decision |")
    L.append("|---|---|---|---|---|---|")
    for fam in facts.FAMILIES:
        d = f[fam]
        L.append(f"| {fam} | {d['scored']} | {d['agreements']} | {d['misses']} | {d['pending']} | "
                 f"{d['decision']} (S={d['S']:+.2f}) |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(P.run(sys.argv[1:], OUT, build))
