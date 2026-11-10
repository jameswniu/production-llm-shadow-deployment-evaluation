#!/usr/bin/env python3
"""harvest.py's medic-phrase rule, so an answer key keeps the medic's own words.

The medic is the automated worker that diagnoses red alerts from scheduled jobs, and its ledger is the
log of every action it took, one note each. shadow-medic, this folder, replays those diagnoses against a
challenger model: harvest.py freezes each past alert as a case, with the medic's note as the answer key
the challenger is scored against, and build_roster lists the names in a case so they can be replaced
with placeholders such as [person1].

The medic writes "Claim RENEWED, not released", "Left RED", "Stays RED pending a real green DONE",
a capitalized word and then words in capitals for emphasis. build_roster read 98 such phrases in the
ledger as names, and answer keys came out as "[person1], not released". A phrase is the medic's only
when it is exactly one of the medic's own two-word phrases (MEDIC_PHRASES, taken from the ledger) or a
case id the medic fixed or applied. Any other shape is minted as before, so real names, names with acronyms and companies
stay redacted. Also pins the given-name skip words ("Will", "May") wherever they sit in a capture.

    python3 shadow-medic/test_medic_phrases.py      exit 0 = all pass
"""
import json
import os
import pathlib
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


def minted(text):
    return sorted(harvest.build_roster(text))


# ---- the medic's phrases are not names ----
MEDIC = ["Claim RENEWED", "Claim RELEASED", "Left RED", "Claim HELD", "Stays RED", "Still NOT", "Closed GREEN",
         "Condition NOT", "Deliberately NOT", "Kept RED", "Ruled OUT", "Newest COMPLETED",
         "Gate NOT", "Verify FAILED", "Fired ONE", "Also CORRECTED", "Fired DETACHED", "Detached XI",
         "Missing DONE", "Still AUTH", "Watch KILLED", "Scheduled RUN"]
for phrase in MEDIC:
    check(f"{phrase!r} is not minted", minted(f"Note. {phrase} at 09:16, nothing else.") == [],
          minted(f"Note. {phrase} at 09:16, nothing else."))
check("a fix id after a medic lead is not minted ('Fix M-20260912T220806')",
      minted("Fix M-20260912T220806 still unverified.") == [], minted("Fix M-20260912T220806 still unverified."))

# The answer key keeps the medic's words, redacted the way harvest redacts it.
note = "Read-back confirms red plus delta. Claim RENEWED, not released, since Jane Smith has not replied."
roster = harvest.build_roster(note)
out = compare.redact_text(note, roster)
check("an answer key keeps 'Claim RENEWED' verbatim", "Claim RENEWED, not released" in out, out)
check("while a real name beside it is still redacted", "Jane" not in out and "Smith" not in out, out)

# ---- every other shape is minted as before ----
for phrase in ("Tavio DONE", "Orvin CA RTR", "Quillfern AI", "Wise SGD", "Notion UI", "Vask VERIFIED ABSENT"):
    check(f"{phrase!r} is still minted", phrase in minted(f"Note. {phrase} today."), minted(f"Note. {phrase} today."))
for phrase in ("Per SKILL", "Ping STAYS RED", "Cap SPENT", "Green DONE", "Delta EMPTY", "Lane REFUSED"):
    check(f"a lead that is also a given name stays minted ({phrase!r})", phrase in minted(f"Note. {phrase} today."),
          minted(f"Note. {phrase} today."))
# Only the exact phrases count. A pair built from a medic word and an emphasis word the medic never
# wrote together can be a person, and so can a longer capture.
for text, want in (("Left HAND replied.", "Left HAND"), ("Evidence GREEN replied.", "Evidence GREEN"), ("So GREEN replied.", "So GREEN"),
                   ("Claim GREEN replied.", "Claim GREEN"), ("Claim RENEWED GREEN replied.", "Claim RENEWED GREEN"),
                   ("Note. Artifacts CHECKED ON DISK today.", "Artifacts CHECKED ON DISK"), ("Note. Tests FAIL today.", "Tests FAIL"),
                   ("Note. Detached XIV today.", "Detached XIV"), ("Note. Jane M-20260912 today.", "Jane M-")):
    check(f"a pair that is not one of the medic's phrases is minted ({want!r})", want in minted(text), minted(text))
leads = {p.split()[0] for p in harvest.MEDIC_PHRASES} | harvest.CASE_ID_LEADS
check("no phrase starts with a two-letter word, which can be a given name", not [w for w in leads if len(w) <= 2], sorted(w for w in leads if len(w) <= 2))
# A fixed copy of macOS's /usr/share/dict/propernames, so this check runs the same on every machine.
given = pathlib.Path(__file__).parent / "testdata" / "given-names.txt"
names = {ln.strip() for ln in given.open() if ln.strip()}
check("no phrase starts with a word on the list of given names", not (leads & names), sorted(leads & names))
check("a medic lead before a name-shaped word is minted ('Claim Jones')", "Claim Jones" in minted("Claim Jones signed."),
      minted("Claim Jones signed."))
check("a medic lead before a capital word outside the list is minted ('Claim SMITH')",
      "Claim SMITH" in minted("Note. Claim SMITH today."), minted("Note. Claim SMITH today."))
check("an emphasis word after a name is no cover ('Tavio RENEWED')", "Tavio RENEWED" in minted("Note. Tavio RENEWED it."),
      minted("Note. Tavio RENEWED it."))

# ---- a skip word that is also a given name, wherever it sits ----
for text, want in (("Will Smith replied.", "Will Smith"), ("Sent Will Smith replied.", "Will Smith"),
                   ("Then May Lee signed.", "May Lee"), ("Then From May Lee signed.", "May Lee")):
    check(f"{text!r} mints {want!r}", want in minted(text), minted(text))
check("'Will NOT' mints nothing", minted("Will NOT retry it.") == [], minted("Will NOT retry it."))

# ---- what the rule does to the live ledger, reported, never a failure ----
ledger = pathlib.Path.home() / "claude-os/state/ping-heal-ledger.jsonl"
if ledger.exists():
    near, kept = set(), set()
    for line in ledger.open():
        if not line.strip():
            continue
        note = json.loads(line).get("note") or ""
        for k in harvest.build_roster(note):
            toks = k.split()
            if len(toks) > 1 and all(re.fullmatch(r"[A-Z][A-Z0-9_-]+", t) for t in toks[1:]):
                (near if toks[0] in leads else kept).add(k)
    print(f"  info  ledger phrases starting like a medic phrase but minted (not on the list): {sorted(near)}")
    print(f"  info  ledger phrases in capitals minted because the lead is not a medic word: {len(kept)}")
else:
    print("  skip  no ledger on this machine, the drift report did not run")

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
