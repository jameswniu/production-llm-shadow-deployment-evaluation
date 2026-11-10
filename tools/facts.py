"""Every number the figures print, computed by compare.py's own code paths.

shadow-medic is the harness that replays a trusted model's diagnoses against a challenger. The medic is that trusted model, a Claude agent that diagnoses failed scheduled jobs and logs a class for each, and the challenger is the candidate model given the same logs.

Rows are read exactly as compare.cmd_scoreboard reads them. As a guard, the totals are cross-checked
against the text cmd_scoreboard prints, so a change in compare.py that this file misses fails loudly.
"""
import contextlib
import io
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
MEDIC = REPO / "shadow-medic"
sys.path.insert(0, str(MEDIC))
import compare  # noqa: E402

MODEL, ENGINE = "glm-5.3", "zai"
P0, P1, ALPHA, BETA = 0.80, 0.92, 0.05, 0.05
FAMILIES = ("ops", "render")


# Stages D, E and F are the avatar video render jobs and form the render family; every other stage is scheduled automation and forms the ops family.
def family_of(stage):
    return "render" if stage in ("D", "E", "F") else "ops"


def read_rows():
    """-> list of dicts for every case with a parseable Class, all splits."""
    rows = []
    results = MEDIC / "results"
    tag = MODEL.replace(":", "-").replace("/", "-")
    for case in sorted((MEDIC / "cases").iterdir()):
        meta_p = case / "meta.json"
        key_p = case / "answer-key.md"
        if not case.is_dir() or not (meta_p.exists() or key_p.exists()):
            continue
        if meta_p.exists():
            try:
                meta = json.loads(meta_p.read_text())
            except ValueError:
                raise SystemExit(f"case {case.name}: meta.json is not valid JSON")
            if not isinstance(meta, dict) or "split" not in meta or "stage" not in meta:
                raise SystemExit(f"case {case.name}: meta.json lacks split or stage")
        else:
            meta = {}
        kc = re.search(r"Class:\s*(MECHANICAL|JUDGMENT)", key_p.read_text()) if key_p.exists() else None
        if not kc:
            if meta_p.exists():
                raise SystemExit(f"case {case.name}: answer-key.md is missing or has no Class: MECHANICAL|JUDGMENT line")
            continue
        split = meta.get("split", "dev")
        stage = meta.get("stage", "?")
        cands = sorted(results.glob(f"shadow-{case.name}-{tag}-{ENGINE}-*.md"))
        if case.name == "q-followup-20260828":
            cands = cands or sorted(results.glob(f"shadow-{tag}-{ENGINE}-*.md"))
        cands = [c for c in cands if not c.name.endswith(".failed.md") and c.stat().st_size > 0]
        got = None
        if cands:
            m = re.search(r"SHADOW_RESULT:[\s*]*(MECHANICAL|JUDGMENT)", cands[-1].read_text())
            got = m.group(1) if m else "none"
        key = kc.group(1)
        result = "PENDING" if got is None else ("MATCH" if got == key else "MISS")
        rows.append({
            "id": case.name, "family": family_of(stage), "stage": stage, "split": split,
            "medic": key, "challenger": got, "result": result,
            "shipped": (case / "input-runlog.txt").exists(),
        })
    return rows


def family_facts(rows, fam, split="holdout"):
    sel = [r for r in rows if r["family"] == fam and (split == "all" or r["split"] == split)]
    scored = [r for r in sel if r["result"] in ("MATCH", "MISS")]
    k = sum(1 for r in scored if r["result"] == "MATCH")
    n = len(scored)
    lo, hi = compare.wilson(k, n)
    la = math.log(BETA / (1 - ALPHA))
    lb = math.log((1 - BETA) / ALPHA)
    s = k * math.log(P1 / P0) + (n - k) * math.log((1 - P1) / (1 - P0))
    decision = "PROMOTE" if s >= lb else "REJECT" if s <= la else "CONTINUE"
    miss = [r for r in scored if r["result"] == "MISS"]
    return {
        "scored": n, "agreements": k, "misses": n - k,
        "pending": sum(1 for r in sel if r["result"] == "PENDING"),
        "decision": decision, "S": round(s, 2),
        "wilson_low": lo, "wilson_high": hi, "rate": (k / n) if n else 0.0,
        "medic_judgment_challenger_mechanical": sum(1 for r in miss if r["medic"] == "JUDGMENT"),
        "medic_mechanical_challenger_judgment": sum(1 for r in miss if r["medic"] == "MECHANICAL"),
    }


def increments():
    return math.log(P1 / P0), math.log((1 - P1) / (1 - P0)), math.log((1 - BETA) / ALPHA)


def cross_check(facts):
    """Compare our totals with the lines compare.cmd_scoreboard itself prints."""
    for fam in FAMILIES:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            compare.cmd_scoreboard(["--family", fam])
        out = buf.getvalue()
        m = re.search(r"agreement (\d+)/(\d+) .* pending=(\d+)", out)
        s = re.search(r"S=([+-][\d.]+)", out)
        f = facts[fam]
        want = (int(m.group(1)), int(m.group(2)), int(m.group(3)), float(s.group(1)))
        got = (f["agreements"], f["scored"], f["pending"], f["S"])
        if want != got:
            raise SystemExit(f"facts.py disagrees with compare.py scoreboard for {fam}: {got} vs {want}")


_CACHE = {}


def load():
    if "f" not in _CACHE:
        rows = read_rows()
        facts = {fam: family_facts(rows, fam) for fam in FAMILIES}
        cross_check(facts)
        _CACHE["f"] = (rows, facts)
    return _CACHE["f"]


def verdict_word(decision):
    return {"CONTINUE": "keep shadowing", "PROMOTE": "promote", "REJECT": "rejected"}[decision]


def decision_color(decision, P):
    return {"CONTINUE": P.ACCENT, "PROMOTE": P.GOOD, "REJECT": P.BAD}[decision]


def case_count():
    return sum(1 for c in (MEDIC / "cases").iterdir() if (c / "meta.json").exists())
