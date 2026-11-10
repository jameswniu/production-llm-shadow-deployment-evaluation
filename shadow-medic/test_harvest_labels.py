#!/usr/bin/env python3
"""Tests how harvest.py, which turns the ledger of the medic's actions on red alerts into cases with
answer keys, picks the class (JUDGMENT or MECHANICAL) for one ledger row.

The medic, the automated worker that diagnoses red alerts, writes a note on each ledger row naming
its class, and that note overrides the class the action verb implies. A note that NEGATES
the word is the medic saying the opposite, and the old substring test read "the documented re-roll
class, not a judgment call" as JUDGMENT. Every negated shape below is one the production ledger
holds; every positive one too. The notes are quoted in the medic's own words: a letter or numeral
such as U or 7 names one of the fleet's scheduled stages, and a carve-out post is the separate
message the medic leaves for the classes its rules single out, auth and judgment.

    python3 shadow-medic/test_harvest_labels.py      exit 0 = all pass
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest  # noqa: E402

passed = failed = 0


def check(name, got, want):
    global passed, failed
    if got == want:
        passed += 1
        print("  ok    " + name)
    else:
        failed += 1
        print("  FAIL  %s (got %s, want %s)" % (name, got, want))


def old_rule(note, action):
    return 'JUDGMENT' if 'JUDGMENT' in (note or '').upper()[:400] else harvest.CLASS_BY_ACTION[action]


L = harvest.ledger_class
reroll = "GLASS VOID-STABILITY HOLD, the documented re-roll class, not a judgment call. Diagnosed from primary evidence"
check("a re-roll whose note says 'not a judgment call' is the action's class, MECHANICAL", L(reroll, "rerun"), "MECHANICAL")
check("which the old substring rule got wrong", old_rule(reroll, "rerun"), "JUDGMENT")
check("'not the auth or judgment class' negates too", L("U got no carve-out post because it is mechanical with a landed fix, "
                                                        "not the auth or judgment class the carve-out names", "closed"), "MECHANICAL")
check("and so does 'not judgment class' after another negated clause",
      L("Not auth_failed and not judgment class, it is induced test noise", "closed"), "MECHANICAL")
check("'non-judgment' negates", L("a non-judgment fault, re-run fired", "rerun"), "MECHANICAL")
check("'judgment class' stated plainly is JUDGMENT over a rerun action",
      L("judgment class (glass void-stability tolerance), no re-run eligible", "rerun"), "JUDGMENT")
check("a negation AFTER the word does not undo it", L("the class is judgment not mechanical", "closed"), "JUDGMENT")
check("a 'no' that ends its own clause does not negate the next one", L("no re-run; judgment class, stays red", "closed"), "JUDGMENT")
check("nor does 'no new ping' before it", L("same fault, no new ping judgment class re-confirmed", "closed"), "JUDGMENT")
check("a positive mention beside a negated one still counts",
      L("not a judgment call at first; reclassified JUDGMENT CLASS after the second hold", "rerun"), "JUDGMENT")
check("lowercase is read the same", L("judgment class, owed by james", "closed"), "JUDGMENT")
check("only the first 400 characters are read, as before", L("x" * 400 + " judgment class", "rerun"), "MECHANICAL")
check("with no mention the action decides: annotated", L("stays red pending the next real green", "annotated"), "JUDGMENT")
check("with no mention the action decides: closed", L("verified green at 10:06", "closed"), "MECHANICAL")
check("an empty note is the action's class", L(None, "rerun"), "MECHANICAL")

print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
