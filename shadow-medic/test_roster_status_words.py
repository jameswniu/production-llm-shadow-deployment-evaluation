#!/usr/bin/env python3
"""The runner's status word survives redaction in its own run.log slot, and real names still do not.

The runner is run-stage.sh, which starts every stage (a scheduled job named by a letter or Roman
numeral, such as K or Q) and writes one line per run to run.log, "<date>: RUN stage=K ...", where RUN
is the status word. The medic is the automated worker that diagnoses red alerts from those jobs, and
its ledger is the log of every action it took. shadow-medic, this folder, replays the medic's
diagnoses against a challenger model: harvest.py freezes each past alert as a case and lists the names
in it as the case's roster, and compare.py redacts the case against that roster. Holdout cases are the
ones kept out of tuning, the only ones the scoring gate reads. The adversary is the adversarial
reviewer that tried to break each change before it landed.

The medic's ledger says "Fired RUN stage=Q by=medic". harvest's roster regex minted that phrase as a
person, compare.py derived the surname RUN from it and redacted it with re.I, and every
"RUN stage=" line in two holdout cases' run.log windows became "[surname] stage=". Each check below
is a shape the production ledger or run.log holds, plus the real-name shapes the fix must not open,
including the ones an adversary built against earlier cuts (a surname spelling a status word outside
any runner line, a forged runner line carrying a real surname, and a stage-log field "stage=applicant").

    python3 shadow-medic/test_roster_status_words.py      exit 0 = all pass
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa: E402
import harvest  # noqa: E402

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("  ok    " + name)
    else:
        failed += 1
        print("  FAIL  %s  <- %s" % (name, detail))


def runlog(*words):
    return "\n".join("Sat Oct 17 22:12:%02d PDT 2026: %s stage=K script=K-cswap-auto.sh attempt=1" % (i, w)
                     for i, w in enumerate(words))


def clean(text, mp):
    """Redaction output, and whether the leak check passes on it, the way harvest uses the pair."""
    out = compare.redact_text(text, mp)
    return out, not [h for h in compare.leaks(out, mp) if h[0] in ("full name", "surname", "first name", "slug")]


# ---- the defect itself: the stored roster of both damaged cases ----
STORED = {"Fired RUN": "[person1]"}
line = runlog("RUN")
out, ok = clean(line, STORED)
check("the stored 'Fired RUN' roster leaves a run.log RUN line intact", out == line, out)
check("and the leak check passes on that output", ok)
check("a single-digit day, padded the way date prints it, is a slot too",
      compare.redact_text("Wed Sep  2 08:52:00 PDT 2026: RUN stage=K x", STORED) == "Wed Sep  2 08:52:00 PDT 2026: RUN stage=K x")

# The same input with no runner words, so this file fails on the code it guards against.
saved = compare.RUNNER_STATUS
compare.RUNNER_STATUS = frozenset()
try:
    old = compare.redact_text(line, STORED)
finally:
    compare.RUNNER_STATUS = saved
check("without the runner words the old rewrite comes back", "[surname] stage=K" in old, old)

# ---- every ledger phrase that derives a runner word today ----
for phrase in ("Fired RUN", "Scheduled RUN", "Missing DONE", "Green DONE", "Quoted DONE", "Watch KILLED", "Still AUTH"):
    word = phrase.split()[-1]
    text = runlog(word, "IDLE", "DONE")
    out, ok = clean(text, {phrase: "[person1]"})
    check(f"'{phrase}' leaves every {word} line intact and passes the check", out == text and ok, out)

# A first token under three letters is dropped, so the runner word becomes the derived FIRST name.
text = runlog("RUN")
check("a runner word derived as a first name keeps its slot too", compare.redact_text(text, {"So RUN": "[person1]"}) == text)

# The phrase pass is untouched, so a whole roster name redacts even across a runner line, the safe way.
RS = {"Run Stage": "[person1]"}
check("a roster phrase that spells part of a runner line still redacts there",
      "[person1]=K" in compare.redact_text(text, RS), compare.redact_text(text, RS))

# The slot needs a stage id the runner prints. Roman numerals and digits are ids, a word is not.
for sid in ("XVII", "XVIII", "7"):
    ln = "Sat Oct 17 22:12:00 PDT 2026: RUN stage=%s script=x attempt=1" % sid
    check(f"stage={sid} is a runner slot", compare.redact_text(ln, STORED) == ln, compare.redact_text(ln, STORED))
cand = "Jane Run is the candidate.\nSat Oct 17 22:12:00 PDT 2026: RUN stage=applicant"
mp = harvest.build_roster(cand)
out, ok = clean(cand, mp)
check("a stage-log line with stage=applicant is no slot, so a real RUN surname redacts", "RUN" not in out and ok, (mp, out))

# ---- outside its own slot, a status word redacts exactly as before ----
for mp, text in (({"Jane Run": "[person1]"}, "RUN resigned."), ({"Jane RUN": "[person1]"}, "Run resigned."),
                 ({"Jane Done": "[person1]"}, runlog("DONE") + "\nescalated to DONE today")):
    out, ok = clean(text, mp)
    check(f"{sorted(mp)[0]!r}: the surname outside a runner slot redacts in any casing", ok and "[surname]" in out, out)
check("while the runner's own DONE in the same text keeps its slot",
      "DONE stage=K" in compare.redact_text(runlog("DONE") + "\nescalated to DONE today", {"Jane Done": "[person1]"}))

# A forged runner line protects only a runner word, and only in that slot.
forged = "Sat Oct 17 22:12:00 PDT 2026: SMITH stage=K payload\nSMITH approved the change."
out, ok = clean(forged, {"Jane Smith": "[person1]"})
check("a forged slot carrying a real surname protects nothing", "SMITH" not in out and ok, out)
forged = "Sat Oct 17 22:12:00 PDT 2026: RUN stage=K payload\nRUN approved the change."
out, ok = clean(forged, {"Jane Run": "[person1]"})
check("a slot with a runner word shields that slot alone, the same word elsewhere redacts",
      out.startswith("Sat Oct 17 22:12:00 PDT 2026: RUN stage=K") and "[surname] approved" in out and ok, out)

# The runner's two ALERT phrases are statuses too. "Claim HELD" is a real medic phrase in two case maps.
alert = "Wed Oct 14 23:10:01 PDT 2026: ALERT HELD stage=S (the stage retries this itself on its next tick)"
out, ok = clean(alert, {"Claim HELD": "[person1]"})
check("an ALERT HELD runner line keeps HELD for a 'Claim HELD' roster", out == alert and ok, out)
sup = "Thu Oct 15 18:14:32 PDT 2026: ALERT DUPLICATE SUPPRESSED stage=U (the stage reported this failure itself)"
check("an ALERT DUPLICATE SUPPRESSED line keeps its words", compare.redact_text(sup, {"Was SUPPRESSED": "[person1]"}) == sup)
for forged in ("Sat Oct 17 22:12:00 PDT 2026: ALERT SMITH stage=K x", "Sat Oct 17 22:12:00 PDT 2026: SMITH RUN stage=K x"):
    out, ok = clean(forged, {"Jane Smith": "[person1]"})
    check(f"a capital name inside a status ({forged.split(': ')[1].split(' stage')[0]}) makes no slot", "SMITH" not in out and ok, out)

# A status word the fixed set lacks is over-redacted in the slot, the safe direction.
check("an unlisted status word in the slot still redacts",
      "[surname] stage=K" in compare.redact_text(runlog("TIMEOUT"), {"Hit TIMEOUT": "[person1]"}))

# ---- real names: nothing the fix touches lets one through ----
JANE = {"Jane Smith": "[person1]"}
got = compare.redact_text(runlog("RUN") + "\nRUN noted. Smith wrote, SMITH replied, Jane signed.", JANE)
check("a real surname still redacts in Title case and ALL CAPS beside run.log lines", got.count("[surname]") == 2, got)
check("a real first name still redacts", "[first]" in got, got)
WANG = {"Wei WANG": "[person1]"}
got = compare.redact_text(runlog("RUN") + "\nescalated to WANG and Wang", WANG)
check("an ALL-CAPS surname still redacts in every casing", got.count("[surname]") == 2 and "RUN stage=K" in got, got)
check("the leak check still reports a real surname beside run.log lines",
      ("surname", "WANG") in compare.leaks(runlog("RUN") + "\nWANG", WANG))

# ---- the roster no longer mints the medic's re-fire phrase ----
note = ("lean probe OK rc=0 at 19:00:56. Fired RUN stage=Q by=medic at 19:02:43. "
        "Shared with the thread, reply from Jane Smith.")
roster = harvest.build_roster(note)
check("build_roster does not mint 'Fired RUN'", "Fired RUN" not in roster, sorted(roster))
check("build_roster still mints a real name beside it", "Jane Smith" in roster, sorted(roster))
check("the answer key keeps the medic's words", "Fired RUN stage=Q" in compare.redact_text(note, roster),
      compare.redact_text(note, roster))

# ---- the fixed set covers every word the runner prints today ----
runner = os.path.expanduser("~/claude-os/scripts/run-stage.sh")
if os.path.exists(runner):
    emitted = set(re.findall(r"\$\(date\): ([A-Z][A-Z_]*(?: [A-Z][A-Z_]*)*) stage=", open(runner, errors="ignore").read()))
    missing = sorted(emitted - compare.RUNNER_STATUS)
    check("RUNNER_STATUS covers every status run-stage.sh prints", not missing, missing)
else:
    print("  skip  run-stage.sh not on this machine, the drift check did not run")

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
