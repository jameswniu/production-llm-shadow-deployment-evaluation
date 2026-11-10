#!/usr/bin/env python3
"""compare.py's single-token name matching, the part of redaction that catches a name outside its full
roster phrase.

shadow-medic, this folder, replays the medic's diagnoses against a challenger model. The medic is the
automated worker that diagnoses red alerts from the fleet, the scheduled jobs in claude-os (the private
repo of automation stages this harness studies), and every model call it makes carries a spending-cap
flag, --max-budget-usd. Each past alert is frozen as a case, and its roster lists the names found in it,
each replaced by a placeholder such as [first] or [surname] when the case is redacted. The runner,
run-stage.sh, starts every stage (a scheduled job named by a letter or Roman numeral) and names its
script and log after it (K-cswap-auto.sh). The template is the fixed prompt text every case is pasted
into, and the preflight is the check run on that built prompt before it leaves the machine.
pii-patterns.sh is claude-os's own redaction list, whose common-word rule leaves a name's lowercase
spelling alone when that spelling is a dictionary word. The adversary is the adversarial reviewer that
tried to break each change before it landed. harvest.py builds each case: it redacts the case's files
and then runs the leak check on the result, keeping the case only when nothing is left. run-shadow.sh
is the script that builds a case's prompt from the template and sends it to the challenger model.

Two gaps let a real name through. First names matched only as written, so "JANE" or "jane" passed, and
two-letter tokens were dropped, so "Li Wang" left "WANG" and "Li" behind. And a token that appeared in
lowercase anywhere in a file, or inside a slug, was dropped for the whole file, so "Held" beside the
verb "held" was never redacted, and "jane-smith" hid inside the very slug it sat in. Each check below is
one of those shapes, or one of the things the old filter protected that must stay protected: the
runner's script and log names, the redactor's own placeholders, and the template prose at the preflight.
The adversary's shapes against the first cut are pinned too: a name inside a file name that only looks
like a stage file, names run together in any casing, a placeholder word, a machine with no word list,
a phone number redact_text left in place, and a name built across two slots of the prompt.

    python3 shadow-medic/test_redaction_names.py      exit 0 = all pass
"""
import json
import os
import shutil
import sys
import tempfile
import pathlib
import re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare  # noqa: E402

# Every case runs against one fixed word list, the words these cases look up, cut from macOS's
# /usr/share/dict/words. Machines ship different lists and a CI runner ships none, so without the pin a
# lowercase-word case would pass on one machine and fail on another.
compare._dict_cache[:] = [frozenset((pathlib.Path(HERE) / "testdata" / "words.txt").read_text().split())]

passed = failed = 0
NAME_KINDS = ("full name", "surname", "first name", "short name", "slug")


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("  ok    " + name)
    else:
        failed += 1
        print("  FAIL  %s  <- %s" % (name, detail))


def clean(text, mp):
    """Redaction output, and whether the leak check then passes on it, the same pair harvest.py runs
    on every case it builds."""
    out = compare.redact_text(text, mp)
    return out, not [h for h in compare.leaks(out, mp) if h[0] in NAME_KINDS]


# ---- first names in every casing ----
TAVIO = {"Tavio Quenneville": "[person1]"}
for text in ("TAVIO approved it.", "tavio approved it.", "Tavio approved it.", "tAvIo approved it."):
    out, ok = clean(text, TAVIO)
    check(f"a first name in {text.split()[0]!r} casing redacts", out.startswith("[first]") and ok, out)
JANE = {"Jane Smith": "[person1]"}
for text in ("JANE approved it.", "Jane approved it.", "jAnE approved it."):
    out, ok = clean(text, JANE)
    check(f"a dictionary-word first name redacts in {text.split()[0]!r} casing", out.startswith("[first]") and ok, out)
if compare._dictionary():
    # The fleet's common-word oracle (pii-patterns.sh): a name that is also a dictionary word stays as
    # written in lowercase prose. Pinned so a change to that rule is a decision, not an accident.
    check("a dictionary-word first name is left alone in lowercase prose, as the fleet's oracle rules",
          compare.redact_text("jane approved it.", JANE) == "jane approved it.")
check("a CamelCase handle keeps its old reach ('JaneProfile')", compare.redact_text("JaneProfile posted", JANE) == "[first]Profile posted",
      compare.redact_text("JaneProfile posted", JANE))
check("and a name from an all-lowercase entry keeps it too ('orvinProfile')",
      compare.redact_text("owner=orvinProfile", {"orvin dalcroft": "[person1]"}) == "owner=[first]Profile",
      compare.redact_text("owner=orvinProfile", {"orvin dalcroft": "[person1]"}))
out, ok = clean("JaneSmith posted", JANE)
check("a handle holding the whole name goes whole, leaving no surname behind ('JaneSmith')", "Smith" not in out and "Jane" not in out and ok, out)
MARCH = {"March Quenneville": "[person1]"}
check("a capitalized first name does not match inside a longer capitalized word ('MARCHED')",
      compare.redact_text("MARCHED OVER", MARCH) == "MARCHED OVER", compare.redact_text("MARCHED OVER", MARCH))
check("the leak check agrees on 'JANE'", ("first name", "Jane") in compare.leaks("JANE approved it.", JANE))

# ---- two-letter names ----
LI = {"Li Wang": "[person1]"}
for text, gone in (("WANG resigned.", "WANG"), ("Wang resigned.", "Wang"), ("Li replied.", "Li"), ("LI replied.", "LI")):
    out, ok = clean(text, LI)
    check(f"'Li Wang' leaves no {gone!r} in {text!r}", gone not in out and ok, out)
out, ok = clean("Wu said yes, WU agreed.", {"Jane Wu": "[person1]"})
check("a two-letter surname redacts as written and in capitals", "Wu" not in out and "WU" not in out and ok, out)
check("a two-letter word is never a short name ('So')", compare.redact_text("So the stage ran.", {"So Jane": "[person1]"}) == "So the stage ran.",
      compare.redact_text("So the stage ran.", {"So Jane": "[person1]"}))
out, ok = clean("Li replied.", {"Jane Li's": "[person1]"})
check("a map entry carrying a possessive still reaches the bare name ('Jane Li's')", "Li" not in out and ok, out)

# ---- possessives: the written token still matches, the bare one now matches too ----
for mp, text, gone in (({"Jane Smith's": "[person1]"}, "Smith replied later.", "Smith"),
                       ({"Jane Smith's": "[person1]"}, "smith's reply followed.", "smith"),
                       ({"Jane Lee's": "[person1]"}, "LEE'S reply followed.", "LEE"),
                       ({"Jane Lee's": "[person1]"}, "Lee replied.", "Lee")):
    out, ok = clean(text, mp)
    check(f"{sorted(mp)[0]!r} leaves no {gone!r} in {text!r}", gone not in out and ok, out)

# ---- a name that is also a word ----
FROST = {"Jane Frost": "[person1]"}
out, ok = clean("The frost came. Frost signed, FROST approved, fRoSt too.", FROST)
check("a name that is also a word redacts in every casing but lowercase",
      "Frost signed" not in out and "FROST" not in out and "fRoSt" not in out and ok, out)
check("and its lowercase word is left alone", "The frost came." in out, out)
# Where the word list has no entry (an irregular form like "held"), the token is treated as a name and
# its lowercase spelling redacts too. That errs toward redaction, never toward a leak.
out, ok = clean("The job held. HELD approved.", {"Jane Held": "[person1]"})
check("a word the list does not know redacts in every casing, the safe way", "held" not in out.lower() and ok, out)
MAXQ = {"Max Quenneville": "[person1]"}
FLAG = "the prep agent exhausted --max-budget-usd at 4.0"
check("the medic's --max-budget-usd flag survives a roster holding a Max", compare.redact_text(FLAG, MAXQ) == FLAG
      and compare.leaks(FLAG, MAXQ) == [], compare.redact_text(FLAG, MAXQ))
for text in ("ran --max-budget-usd=0.50 then", "curl --max-time 90 x", "chess.sh --max-ply 4"):
    check(f"each flag the stage logs carry survives too ({text.split()[1].split('=')[0]})",
          compare.redact_text(text, MAXQ) == text and compare.leaks(text, MAXQ) == [], compare.redact_text(text, MAXQ))
for text in ("max approved the change.", "Max wrote, MAX signed, mAx agreed.", "ran --max-other 3", "ran --max-budget-usd-old"):
    out, ok = clean(text, MAXQ)
    check(f"anything but an exact flag still redacts a Max, lowercase included ({text!r})", "max" not in out.lower() and ok, out)
for text in ("ran --max-budget-usd.evil then", "ran --max-budget-usd:x then", "ran --max-budget-usd/x then"):
    out, ok = clean(text, MAXQ)
    check(f"a flag running on into more text is no flag ({text.split()[1]!r})", "max" not in out.lower() and ok, out)
out, ok = clean("curl --max-time 90", {"Max Time": "[person1]"})
check("a flag spelled like a roster name is not protected", "max" not in out.lower() and "time" not in out.lower() and ok, out)
logs = sorted((pathlib.Path.home() / "claude-os/output").glob("*.log"))
if logs:
    seen = set()
    for lp in logs:
        seen |= set(re.findall(r"(?<![\w-])-{2}max-[a-z0-9]+(?:-[a-z0-9]+)*(?![\w-])", lp.read_text(errors="ignore")))
    check(f"every max flag the {len(logs)} stage logs carry is in CLI_FLAGS", seen <= compare.CLI_FLAGS, sorted(seen - compare.CLI_FLAGS))
else:
    print("  skip  no claude-os stage logs here, the flag drift check did not run")
out, ok = clean("max wrote, then Max and MAX signed.", {"max quenneville": "[person1]"})
check("a Max from an all-lowercase roster entry redacts in every casing, lowercase included", "max" not in out.lower() and ok, out)
LEE = {"Jane Lee": "[person1]"}
out, ok = clean("LEE approved, Lee signed, the lee shore.", LEE)
check("a COMMON surname redacts in capitals too, not only as written", "LEE" not in out and "Lee signed" not in out and ok, out)
check("and stays a word in lowercase", "the lee shore" in out, out)

# ---- slugs and middle names ----
for text in ("owner=jane-smith", "see jane-smith-designer now", "path /u/jane-smith/x"):
    out, ok = clean(text, JANE)
    check(f"a name in a lowercase slug redacts ({text!r})", "jane" not in out and "smith" not in out and ok, out)
out, ok = clean("Alice approved it.", {"Jane Alice Smith": "[person1]"})
check("a middle name redacts on its own", "Alice" not in out and ok, out)

# ---- what the old filter protected stays protected ----
run = "Sat Oct 17 22:12:00 PDT 2026: RUN stage=K script=K-cswap-auto.sh attempt=1"
check("a fleet script name keeps a roster token inside it ('K-cswap-auto.sh')",
      compare.redact_text(run, {"Cswap MacPro": "[person1]"}) == run, compare.redact_text(run, {"Cswap MacPro": "[person1]"}))
check("a stage log name too ('XVII-macpro-door.log')",
      compare.redact_text("tail XVII-macpro-door.log", {"Door Macpro": "[person1]"}) == "tail XVII-macpro-door.log")
out, ok = clean("ran X-jane-smith.sh last", JANE)
check("a script-shaped name that carries a roster name is not protected", "jane" not in out and ok, out)
out = compare.redact_text("[first] wrote, First signed", {"Jane First": "[person1]"})
check("the redactor's own placeholders are never eaten", out.startswith("[first] wrote") and "First" not in out, out)
check("a word-like token from an all-lowercase entry keeps its old behaviour ('this shape')",
      compare.redact_text("this is it. This works.", {"this shape": "[person1]"}) == "this is it. This works.")
out, ok = clean("Orvin wrote back.", {"orvin dalcroft": "[person1]"})
check("a name from an all-lowercase entry still redacts when it is not a word", "Orvin" not in out and ok, out)
out, ok = clean("orvin wrote, then Orvin and ORVIN signed.", {"orvin dalcroft": "[person1]"})
check("and written once on its own in lowercase it does not make itself a word", "orvin" not in out.lower() and ok, out)
check("the leak check agrees on a lowercase entry's name standing alone",
      ("first name", "orvin") in compare.leaks("orvin wrote.", {"orvin dalcroft": "[person1]"}))

# ---- only the runner's own stage files are protected, never a file name of the same shape ----
VASK = {"Orvin Vask": "[person1]"}
for text, mp, gone in (("script=X-tavioquenneville.sh", TAVIO, "tavioquenneville"), ("Applicant file: VASK-notes.py", VASK, "VASK"),
                       ("ran VASK-notes.log", VASK, "VASK"), ("ran X-orvin-vask.sh", VASK, "vask")):
    out, ok = clean(text, mp)
    check(f"a name in a file name that is not a stage file redacts ({text!r})", gone not in out and ok, out)
check("a stage file stays whole even when one roster entry holds two of its words",
      compare.redact_text("tail XVII-macpro-door.log", {"Macpro Door": "[person1]"}) == "tail XVII-macpro-door.log")
CSWAP = {"Cswap Tavio": "[person1]"}
check("a stage file at the end of a sentence stays whole", compare.redact_text("ran K-cswap-auto.sh.", CSWAP) == "ran K-cswap-auto.sh.")
for text in ("ran K-cswap-auto.sh.bak", "ran K-cswap-auto.log-old"):
    check(f"a longer name that starts like a stage file is ordinary text ({text!r})",
          "cswap" not in compare.redact_text(text, CSWAP), compare.redact_text(text, CSWAP))
out, ok = clean("ran K-cswap-auto.sh'ara replied", {"Tavio Sh'ara": "[person1]"})
check("a surname written straight after a stage file's .sh is not shielded by it", "sh'ara" not in out.lower() and ok, out)
check("a protected span shields only a match lying wholly inside it",
      len(compare._outside_slots(r"auto\.sh now", "run K-cswap-auto.sh now")) == 1
      and not compare._outside_slots(r"cswap", "run K-cswap-auto.sh now"))
# This public copy lists only the jobs named in its published incidents, so the drift check runs only
# when SHADOW_RUNNER points at a fleet runner whose stage table should match STAGE_FILES exactly.
import os
stage_sh = pathlib.Path(os.environ["SHADOW_RUNNER"]) if os.environ.get("SHADOW_RUNNER") else None
if stage_sh and stage_sh.exists():
    table = set(re.findall(r'^\s+[0-9A-Z]+\) SCRIPT="([^"]+)\.sh" ;;', stage_sh.read_text(), re.M))
    check("STAGE_FILES is exactly run-stage.sh's stage table", table == set(compare.STAGE_FILES),
          f"missing {sorted(table - compare.STAGE_FILES)}, extra {sorted(compare.STAGE_FILES - table)}")
else:
    print("  skip  no fleet runner given (SHADOW_RUNNER), the stage-table drift check did not run")

# ---- run together, in capitals, or two letters in odd casing ----
for text in ("JANESMITH wrote.", "see janesmith now", "jane wrote, as janesmith"):
    out, ok = clean(text, JANE)
    check(f"two tokens of one name run together redact in any casing ({text!r})", "smith" not in out.lower() and ok, out)
for text in ("see liwang now", "see wangli now", "LIWANG wrote"):
    out, ok = clean(text, LI)
    check(f"a two-letter name run into its surname redacts ({text!r})", "wang" not in out.lower() and ok, out)
OLA = {"Ola Vey": "[person1]"}
for text, mp, gone in (("OlaVey wrote", OLA, "vey"), ("see veyola now", OLA, "vey"), ("LIWU wrote", {"Li Wu": "[person1]"}, "wu"),
                       ("see janealicesmith now", {"Jane Alice Smith": "[person1]"}, "alice")):
    out, ok = clean(text, mp)
    check(f"tokens of one name run together redact whatever their length ({text!r})", gone not in out.lower() and ok, out)
ZOR, ZB = {"Zor-Vin Dalq": "[person1]"}, {"Zorvin Dalq": "[person1]", "Borin Quxx": "[person2]"}
for text, mp, gone in (("see zor-vindalq now", ZOR, "dalq"), ("see zor-vin-dalq now", ZOR, "dalq"),
                       ("zorvindalqborin wrote", ZB, "borin"), ("ZorvinDalqBorin wrote", ZB, "borin")):
    out, ok = clean(text, mp)
    check(f"a hyphenated token, or three names, run together redact ({text!r})", gone not in out.lower() and ok, out)
check("two two-letter names of different people run together are left to the token passes",
      compare.redact_text("liwu x", {"Li Ng": "[person1]", "Bo Wu": "[person2]"}) == "liwu x")
check("a slug of a thousand repeated tokens redacts without exhausting the stack",
      compare.redact_text("jane" * 1000 + "smith", JANE) == "[slug]")
out, ok = clean("OlaQuenneville wrote", {**OLA, **TAVIO})
check("a part one token pass exposes is taken by the next, so the output passes the check", "quenneville" not in out.lower() and ok, out)
out, ok = clean("see jane-quenneville now", {"Jane Quenneville": "[person1]"})
check("a slug whose first part is a word and whose second is not goes whole", "jane" not in out and "quenneville" not in out and ok, out)
for text, mp, gone in (("owner=lee_smith", {"Lee Smith": "[person1]"}, "smith"), ("x tavio_quenneville y", TAVIO, "quenneville"),
                       ("QUENNEVILLE_NOTES", TAVIO, "quenneville")):
    out, ok = clean(text, mp)
    check(f"an underscore joins a name like a hyphen ({text!r})", gone not in out.lower() and ok, out)
out, ok = clean("lI replied, the li tag stays.", LI)
check("a two-letter name redacts in mixed case and stays a word in lowercase", "lI" not in out and "the li tag" in out and ok, out)

# ---- the redactor's own placeholders never make a roster token a word ----
for mp in ({"Jane Person": "[person1]", "Total Query Cost": "[person2]"}, {"orvin person": "[person1]", "Total Query Cost": "[person2]"}):
    out, ok = clean("Gmail Total Query Cost failed.\nPERSON replied.", mp)
    check(f"a surname spelled like a placeholder word still redacts beside one ({sorted(mp)[0]!r})", "PERSON" not in out and ok, out)

# ---- with no word list, only COMMON is a word, and every other token redacts in lowercase too ----
saved = list(compare._dict_cache)
compare._dict_cache[:] = [frozenset()]
try:
    out, ok = clean("The frost came. Frost signed.", FROST)
    check("no word list: a name redacts even in lowercase prose, the safe direction", "frost" not in out.lower() and ok, out)
    out, ok = clean("the lee shore, Lee signed.", LEE)
    check("no word list: a COMMON word still stays a word in lowercase", "the lee shore" in out and "Lee signed" not in out and ok, out)
finally:
    compare._dict_cache[:] = saved

# ---- structure: whatever leaks() reports, redact_text removes ----
JS = "call (415) 555-0134 or 415-555-0134, mail jane.smith@example.com"
out = compare.redact_text(JS, JANE)
check("phones and a whole address redact, the domain with them", compare.leaks(out, JANE) == [] and "example" not in out and "555" not in out, out)

# ---- the preflight holds template prose to whole names only ----
tmp = pathlib.Path(tempfile.mkdtemp(prefix="shadow-test-"))
try:
    case = tmp / "Z-20260101T0000"
    case.mkdir()
    (case / "input-runlog.txt").write_text("Sat Oct 17 22:12:00 PDT 2026: RUN stage=K script=K-cswap-auto.sh attempt=1")
    (case / "input-qlog.txt").write_text("nothing here")
    (case / "input-code.txt").write_text("(no code excerpt for this case)")
    (case / "meta.json").write_text(json.dumps({"stage": "K", "script": "K-cswap-auto.sh", "log": "K-cswap-auto.log"}))
    tmpl_words = [w for w in ("Verify", "Watch", "Record", "Reply") if w in (pathlib.Path(HERE) / "prompt-template.md").read_text()]
    word = tmpl_words[0] if tmpl_words else "Verify"
    mp = {word + " Jones": "[person1]"}
    built = compare.built_prompt(case)
    check("the built prompt rebuilds byte for byte", built is not None and built[0].count(word) >= 1)
    hits = compare.prompt_leaks(built[0] + "\n", case, mp)
    check(f"a template word that is also a roster token ({word!r}) does not block the case", hits == [], hits)
    check("a prompt that does not rebuild gets the full check, template words included",
          any(h[1] == word for h in compare.prompt_leaks(built[0] + "\nextra", case, mp)))
    (case / "input-qlog.txt").write_text(f"{word} said so")
    built = compare.built_prompt(case)
    check("the same token in the case's own evidence is still caught",
          any(h[1] == word for h in compare.leaks((case / "input-qlog.txt").read_text(), mp)))
    check("and in the built prompt, where it fills a slot", any(h[1] == word for h in compare.prompt_leaks(built[0], case, mp)))

    def shadow_build(c):
        """A copy of the prompt builder in run-shadow.sh, the script that sends a case to the challenger
        model, which fills the template's slots one after another."""
        t = (pathlib.Path(HERE) / "prompt-template.md").read_text()
        meta = json.loads((c / "meta.json").read_text())
        t = t.replace("{STAGE_LOG}", meta.get("log") or "the stage log").replace("{SCRIPT}", meta.get("script") or "the stage script")
        for k, f in (("RUNLOG", "input-runlog.txt"), ("QLOG", "input-qlog.txt"), ("CODE", "input-code.txt")):
            t = t.replace("{" + k + "}", (c / f).read_text())
        return t

    (case / "input-runlog.txt").write_text("Ta{QLOG}")
    (case / "input-qlog.txt").write_text("vio")
    sent = shadow_build(case)
    check("a name built across two case files by a slot marker is caught in the prompt",
          "Tavio" in sent and any(h[1] == "Tavio" for h in compare.prompt_leaks(sent, case, TAVIO)), compare.prompt_leaks(sent, case, TAVIO))
    (case / "input-runlog.txt").write_text("vio")
    (case / "input-qlog.txt").write_text("nothing here")
    (case / "meta.json").write_text(json.dumps({"stage": "K", "script": "Ta{RUNLOG}", "log": "K-cswap-auto.log"}))
    sent = shadow_build(case)
    check("and one built from a meta label and a case file",
          "Tavio" in sent and any(h[1] == "Tavio" for h in compare.prompt_leaks(sent, case, TAVIO)), compare.prompt_leaks(sent, case, TAVIO))
    for bad in ("{not json", json.dumps({"stage": "K", "script": "K-cswap-auto.sh", "log": 5}), json.dumps(["K"])):
        (case / "meta.json").write_text(bad)
        try:
            hits, err = compare.prompt_leaks("Tavio wrote", case, TAVIO), None
        except Exception as e:
            hits, err = None, e
        check(f"a meta.json the builder cannot read gets the full check, not a crash ({bad[:16]!r})",
              compare.built_prompt(case) is None and err is None and ("first name", "Tavio") in hits, err or hits)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
