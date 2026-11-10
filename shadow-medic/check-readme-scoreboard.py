#!/usr/bin/env python3
"""Fail if the README's scoreboard block has drifted from what compare.py actually prints.

The README quotes real terminal output. Re-harvesting or re-scoring changes those numbers,
and frozen prose rots silently. This is the regression: run it after any harvest or scoring
pass. Exits 1 on drift and prints both sides.
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
README = HERE.parent / "README.md"

# Both families are required, not discovered. A guard that scores whatever blocks it happens to
# find can be satisfied by DELETING the unflattering one, which is the failure this page exists
# to argue against: render is the rejected family, so it is the block most tempting to drop.
REQUIRED_FAMILIES = {"ops", "render"}


def quoted_blocks(text):
    """-> ({family: [lines]}, [duplicate families]) for the scoreboard invocations in the README."""
    out = {}
    dupes = []
    fam = None
    for line in text.splitlines():
        m = re.match(r"\$ \./compare\.py scoreboard --family (\w+)", line.strip())
        if m:
            fam = m.group(1)
            if fam in out:
                dupes.append(fam)
            out[fam] = []
            continue
        if fam:
            if line.strip().startswith("$") or line.strip() == "```":
                fam = None
            elif line.strip():
                out[fam].append(line.rstrip())
    return out, dupes


def live_block(family):
    r = subprocess.run(
        [sys.executable, str(HERE / "compare.py"), "scoreboard", "--family", family],
        capture_output=True, text=True,
    )
    # 0 and 1 are verdicts (promote / continue-or-reject), not failures. 2+ is a broken run.
    if r.returncode > 1:
        print(f"compare.py scoreboard --family {family} exited {r.returncode}", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        sys.exit(2)
    keep = ("[holdout]", "SPRT ")
    return [ln.rstrip() for ln in r.stdout.splitlines() if ln.startswith(keep)]


SVG = README.parent / "media" / "sprt-axis.svg"


def svg_claims():
    """-> {family: (agreements, n, S)} read off the axis graphic, or {} when it is absent.

    The picture carries the same numbers as the text block and nothing was checking it, so a
    re-score would have left a chart that quietly disagreed with the scoreboard beside it. A
    figure is a claim; it gets the same guard the prose does.
    """
    try:
        s = SVG.read_text()
    except FileNotFoundError:
        return {}
    out = {}
    for fam in ("ops", "render"):
        m = re.search(
            r">" + fam + r"</text>.*?>\s*(\d+)\s+of\s+(\d+)\s*&#183;\s*S\s*=\s*([+-][\d.]+)\s*<",
            s, re.S)
        if m:
            out[fam] = (int(m.group(1)), int(m.group(2)), float(m.group(3)))
    return out


def check_svg(live):
    """live: {family: (agreements, n, S)} parsed from compare.py. Returns count of drifted rows."""
    claims = svg_claims()
    # Fail CLOSED when the README embeds the figure. Skipping on "absent or unparseable" meant a
    # deleted or re-drawn axis passed the checker while the page still showed it and still claimed
    # the numbers were enforced, which is the exact shape of lie this guard exists to catch.
    embedded = "media/sprt-axis.svg" in README.read_text()
    if not claims:
        if embedded:
            print("DRIFT [figure] README embeds media/sprt-axis.svg but no readable claims were "
                  "found in it (missing file, or a layout this checker cannot parse)")
            return 1
        print("README does not embed the axis figure, skipping the figure check")
        return 0
    if embedded:
        missing = REQUIRED_FAMILIES - set(claims)
        if missing:
            print(f"DRIFT [figure] the axis is missing required famil(ies): {sorted(missing)}")
            return 1 + len(missing)
    drift = 0
    for fam, want in sorted(claims.items()):
        got = live.get(fam)
        if got is None:
            print(f"DRIFT [figure {fam}] the graphic names a family the scoreboard did not report")
            drift += 1
        elif want != got:
            drift += 1
            print(f"DRIFT [figure {fam}] svg says {want[0]}/{want[1]} S={want[2]:+.2f}, "
                  f"compare.py says {got[0]}/{got[1]} S={got[2]:+.2f}")
        else:
            print(f"ok [figure {fam}] {want[0]}/{want[1]} S={want[2]:+.2f}")
    return drift


BADGE_LABELS = ("incidents", "held_out", "ops", "render", "tests")
BADGE_RE = re.compile(r"https://img\.shields\.io/badge/([A-Za-z_]+)-([^-\s)\"]+)-[A-Za-z0-9]+")


def _decode_badge(v):
    return v.replace("_", " ").replace("%2F", "/").replace("%C2%B7", "\u00b7")


def live_badge_values(live):
    """-> {label: callable returning the live value}. Lazy, so the ten second test run only happens if needed."""
    tools = HERE.parent / "tools"
    sys.path.insert(0, str(tools))
    import facts  # noqa: E402
    rows, f = facts.load()
    held = [r for r in rows if r["split"] == "holdout"]

    def tests():
        # Run under an empty home with no fleet runner, so the checks that need this machine's private
        # fleet skip here exactly as they do in CI, and the count is the same everywhere.
        import os
        import tempfile
        env = {k: v for k, v in os.environ.items() if k != "SHADOW_RUNNER"}
        with tempfile.TemporaryDirectory() as home:
            env["HOME"] = home
            r = subprocess.run(["bash", "run-tests.sh"], cwd=HERE, capture_output=True, text=True, env=env)
        return str(sum(int(n) for n in re.findall(r"(\d+) passed", r.stdout + r.stderr)))

    return {
        "incidents": lambda: str(facts.case_count()),
        "held_out": lambda: str(len(held)),
        "ops": lambda: f"{f['ops']['agreements']}/{f['ops']['scored']}",
        "render": lambda: f"{f['render']['agreements']}/{f['render']['scored']}",
        "tests": tests,
    }


def check_badges(live):
    """Compare shields.io badge values in the README with live values. Absent labels are skipped."""
    found = {}
    counts = {}
    for label, value in BADGE_RE.findall(README.read_text()):
        if label in BADGE_LABELS:
            counts[label] = counts.get(label, 0) + 1
            if label not in found:
                found[label] = _decode_badge(value)
    drift = 0
    for label in BADGE_LABELS:
        if counts.get(label, 0) > 1:
            drift += 1
            print(f"DRIFT [badge {label}] appears {counts[label]} times in the README")
    live_vals = live_badge_values(live) if found else {}
    for label in BADGE_LABELS:
        if label not in found:
            print(f"skip [badge {label}] not in the README")
            continue
        want, got = found[label], live_vals[label]()
        if want == got:
            print(f"ok [badge {label}] {got}")
        else:
            drift += 1
            print(f"DRIFT [badge {label}] README says {want}, live is {got}")
    return drift


def check_figures():
    """Run every generator with --check; any non-zero exit is drift."""
    tools = HERE.parent / "tools"
    scripts = sorted(tools.glob("render_*.py")) + [tools / "verdicts_table.py"]
    drift = 0
    for sc in scripts:
        if not sc.exists():
            continue
        r = subprocess.run([sys.executable, str(sc), "--check"], capture_output=True, text=True)
        if r.returncode:
            drift += 1
            print(f"DRIFT [generator {sc.name}] exited {r.returncode}")
            print(r.stdout[-1500:])
        else:
            print(f"ok [generator {sc.name}]")
    return drift


def parse_live(lines):
    """-> (agreements, n, S) from a family's two summary lines."""
    a = re.search(r"agreement\s+(\d+)/(\d+)", " ".join(lines))
    s = re.search(r"S=([+-][\d.]+)", " ".join(lines))
    if not (a and s):
        return None
    return int(a.group(1)), int(a.group(2)), float(s.group(1))


def main():
    quoted, dupes = quoted_blocks(README.read_text())
    found = set(quoted)
    missing = REQUIRED_FAMILIES - found
    unexpected = found - REQUIRED_FAMILIES
    if missing or unexpected or dupes:
        if missing:
            print(f"README scoreboard is missing required famil(ies): {sorted(missing)}", file=sys.stderr)
        if unexpected:
            print(f"README scoreboard quotes unknown famil(ies): {sorted(unexpected)}", file=sys.stderr)
        if dupes:
            print(f"README scoreboard quotes famil(ies) twice: {sorted(set(dupes))}", file=sys.stderr)
        print("Every required family must be quoted exactly once.", file=sys.stderr)
        return 2
    drift = 0
    live = {}
    for family, want in quoted.items():
        got = live_block(family)
        parsed = parse_live(got)
        if parsed:
            live[family] = parsed
        if want != got:
            drift += 1
            print(f"DRIFT [{family}]")
            print("  README says:")
            for ln in want:
                print(f"    {ln}")
            print("  compare.py prints:")
            for ln in got:
                print(f"    {ln}")
        else:
            print(f"ok [{family}] {len(want)} lines match")
    drift += check_svg(live)
    drift += check_badges(live)
    drift += check_figures()
    if drift:
        print(f"\n{drift} claim(s) stale. Update the README scoreboard and the axis figure, then re-run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
