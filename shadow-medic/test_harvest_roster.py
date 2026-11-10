#!/usr/bin/env python3
"""harvest.py's build_roster, the per-case list of names every case input is redacted against.

shadow-medic, this folder, is a harness that replays the medic's diagnoses against a challenger model,
where the medic is the automated worker that diagnoses red alerts from scheduled jobs. harvest.py turns
the medic's past alerts into cases (frozen logs plus the medic's note as the answer key), and
build_roster lists the names in a case's text so each can be replaced with a placeholder such as
[person1] before anything leaves the machine. A capture is a run of capitalized words the roster's
pattern picks up as a possible name.

A capture whose first word is on the skip list ("Sent", "Then", "From") used to be dropped whole,
and finditer resumes after a match, so the name behind the skip word was never minted and went out
unredacted. These checks pin that the skip word is peeled off and the rest judged like any other
candidate, and that everything the skip list exists to stop is still stopped.

    python3 shadow-medic/test_harvest_roster.py      exit 0 = all pass
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


def minted(text):
    return sorted(harvest.build_roster(text))


def clean(text):
    """Redaction with the roster built from the same text, and whether the leak check then passes."""
    mp = harvest.build_roster(text)
    out = compare.redact_text(text, mp)
    return out, not [h for h in compare.leaks(out, mp) if h[0] in ("full name", "surname", "first name", "slug")]


# ---- the gap: a name behind a skip word ----
for text in ("Sent Jane Smith the report.", "Then Jane Smith replied.", "From Jane Smith <x>",
             "Received Jane Smith's note", "With Jane Smith on the call"):
    check(f"{text!r} mints Jane Smith", any(k in ("Jane Smith", "Jane Smith's") for k in minted(text)), minted(text))
    out, ok = clean(text)
    check(f"{text!r} leaves no Jane or Smith behind", "Jane" not in out and "Smith" not in out and ok, out)
check("several skip words in a row are all peeled", minted("Then From Jane Smith wrote.") == ["Jane Smith"],
      minted("Then From Jane Smith wrote."))
check("a three-part name behind a skip word keeps all three", "Mary Ann Lee" in minted("Sent Mary Ann Lee a slot."),
      minted("Sent Mary Ann Lee a slot."))

check("a run of skip words longer than the capture still reaches the name",
      "Jane Smith" in minted("Then From With Jane Smith wrote."), minted("Then From With Jane Smith wrote."))
check("a word that cannot start a name is peeled with the skip words ('Then RUN Jane Smith')",
      "Jane Smith" in minted("Then RUN Jane Smith wrote."), minted("Then RUN Jane Smith wrote."))

# A skip word that is also a given name can be the first name itself.
for text, want in (("Will Smith replied.", "Will Smith"), ("May Lee signed.", "May Lee")):
    check(f"{want!r} is minted whole, its given name on the skip list", want in minted(text), minted(text))
    out, ok = clean(text)
    check(f"and {want!r} leaves the text", want.split()[1] not in out and ok, out)
check("a skip given name before a non-name word mints nothing ('Will NOT')", minted("Will NOT retry it.") == [],
      minted("Will NOT retry it."))
check("a possessive capture is minted as written, as before ('Per James's')",
      minted("Per James's request was recorded.") == ["Per James's"], minted("Per James's request was recorded."))

# The old rule, inline, so this file fails on the code it guards against.
OLD = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)?(?: [A-Z][a-zA-Z'-]+){1,3})\b")
skip_words = {"Sent", "Then"}
old = [m.group(1) for m in OLD.finditer("Sent Jane Smith the report.") if m.group(1).split()[0] not in skip_words]
check("the old whole-capture skip minted nothing here", old == [], old)

# ---- what the skip list is for still holds ----
check("a skip word plus one word mints nothing ('No Slack')", minted("No Slack today, then it posted.") == [],
      minted("No Slack today, then it posted."))
check("a skip word plus a single name mints nothing, as a lone first name never did", minted("Sent Jane.") == [])
check("a remainder that does not start like a name mints nothing ('Parent LEFT RED')", minted("Parent LEFT RED") == [])
check("a known non-name behind a skip word stays out ('Then Fired RUN')", minted("Then Fired RUN stage=Q") == [],
      minted("Then Fired RUN stage=Q"))
check("a template phrase behind a skip word stays out ('Then Do NOT')", minted("Then Do NOT retry it.") == [],
      minted("Then Do NOT retry it."))
check("over-inclusive as before, a company behind 'The' is minted", minted("The Quillfern Group called.") == ["Quillfern Group"],
      minted("The Quillfern Group called."))
check("a name with no skip word is minted exactly as before", minted("Jane Smith replied.") == ["Jane Smith"])

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
