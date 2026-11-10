#!/usr/bin/env python3
"""harvest.py [--limit N] [--dry-run]

Turns entries from the ping-heal ledger, the log of every action the medic (the automated
worker that diagnoses red alerts) took on one, into case directories for shadow-medic, this
folder's harness that replays those diagnoses against a challenger model. For each distinct
diagnosable event (stage, first substantive rerun/annotated/closed entry), it
freezes: the run.log window around the event, the stage's own log window, and
the ledger note as the answer key (class from the action: rerun/closed ->
MECHANICAL, annotated -> JUDGMENT). Inputs are auto-redacted with a per-case
roster; a case that fails the leak check or has empty evidence is skipped
loudly, never written half-made.
"""
import json
import os, os, re, sys, subprocess, pathlib, datetime, tempfile, shutil

HOME = pathlib.Path.home()
# claude-os is the private repo of scheduled automation stages this harness studies; the medic's
# ledger and the fleet's run logs live under it. SHADOW_FLEET points at another fleet's root and
# SHADOW_LEDGER at another ledger; the defaults are the author's own fleet.
FLEET = pathlib.Path(os.environ['SHADOW_FLEET']).expanduser() if os.environ.get('SHADOW_FLEET') else HOME / 'claude-os'
LEDGER = pathlib.Path(os.environ['SHADOW_LEDGER']) if os.environ.get('SHADOW_LEDGER') else FLEET / 'state/ping-heal-ledger.jsonl'
OUT_LOG = FLEET / 'output'
CASES = pathlib.Path(__file__).parent / 'cases'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import importlib
cmp_mod = importlib.import_module('compare')

SKIP_STAGES = {None, '', 'shape-audit', 'shape', 'board', 'audit', '-', 'checkpoint', 'glass', 'mystery-daemon', 'drill-chokepoint-summon', 'H'}
CLASS_BY_ACTION = {'rerun': 'MECHANICAL', 'closed': 'MECHANICAL', 'annotated': 'JUDGMENT'}
# A mention of judgment that the note itself negates: "not a judgment call", "not the auth or
# judgment class", "non-judgment". Only spaces or a hyphen may sit between the negator and the word,
# with at most an article and one "X or" before it, so "no re-run; judgment class" stays a mention.
NEGATED_JUDGMENT = re.compile(r"\b(?:NOT|NO|NOR|NEITHER|NEVER|NON)(?:[ -]+(?:A|AN|THE))?(?:[ -]+[A-Z_]+[ -]+OR)?[ -]+JUDGMENT")


def ledger_class(note, action):
    """The answer key's class for one ledger row. The medic names the class in its own note
    ('JUDGMENT CLASS', 'judgment class'), and that is trusted over the action verb, because a
    'closed' or 'rerun' action can be the mechanical AFTERMATH of a judgment red. A mention is not
    a declaration, though: "the documented re-roll class, not a judgment call" is the medic saying
    the opposite, and the plain substring test this replaces read it as JUDGMENT. So mentions the
    note negates are dropped first, and only a mention left standing in the first 400 characters
    overrides the action."""
    u = NEGATED_JUDGMENT.sub(" ", (note or "").upper()[:400])
    return 'JUDGMENT' if 'JUDGMENT' in u else CLASS_BY_ACTION[action]
SCRIPT_BY_STAGE = None  # resolved lazily from run.log RUN lines
SPLIT = 'holdout'   # --split dev can force a case into the tuning set; it can never pull one out

# The tuning commit's tree IS the dev set. Deriving the split from git is what makes "seen"
# auditable, and it is the claim the README already made. Before this, split was only the flag
# default above, so a plain re-harvest silently rewrote every dev case to holdout and moved 15
# tuned-on cases into the gate. Two guards now make that unrepresentable: the tree decides, and
# split_for() is a one-way ratchet that will promote a case to dev but never demote one.
TUNE_COMMIT = os.environ.get('SHADOW_TUNE_COMMIT', '626de28')
# The dev set as a CHECKED-IN, APPEND-ONLY manifest, seeded from the tuning tree. The tree alone
# was not enough: a case minted later with --split dev is not in it, so it stayed dev only by
# reading its own cases/<slug>/meta.json, and a from-scratch re-harvest (no cases dir) would have
# resolved the tree fine, missed the slug, and written it holdout. Provenance has to outlive the
# untracked directory, so --split dev appends here and this file travels with the repo.
DEV_MANIFEST = pathlib.Path(__file__).resolve().parent / 'dev-set.txt'


class SplitUnknown(RuntimeError):
    """Raised when provenance cannot be established. Fails the harvest rather than guessing."""
_DEV_NAMES = None


def manifest_names():
    """Names recorded in the append-only dev manifest. Empty set when the file is absent."""
    try:
        return {l.strip() for l in DEV_MANIFEST.read_text().splitlines() if l.strip()}
    except FileNotFoundError:
        return set()


def remember_dev(name):
    """Append a deliberate --split dev case to the manifest so its provenance survives the
    cases dir being deleted. Append-only and sorted; never removes a name.

    Called ONLY after a case is promoted, never from split_for(). It used to live inside the
    resolver, which meant a --dry-run, a failed leak check, or a Ctrl-C could write a slug into
    the checked-in manifest with no case behind it. Manifest membership then wins forever, so
    that incident would be silently dropped from the holdout gate: contamination in the
    direction that quietly weakens the evidence rather than inflating it.
    """
    names = manifest_names()
    if name in names:
        return
    names.add(name)
    DEV_MANIFEST.write_text("\n".join(sorted(names)) + "\n")


def tree_case_names():
    """Case dir names in the tuning commit's tree, or None when git cannot answer."""
    global _DEV_NAMES
    if _DEV_NAMES is None:
        try:
            # Resolve the repo root from git itself, never from a relative __file__. Invoked as
            # `python3 harvest.py` from inside shadow-medic/, __file__ has no directory part, so
            # CASES.parent.parent collapses to '.' and ls-tree answers with './' instead of case
            # paths: a non-empty set holding no case name, which reads as a working guard while
            # classifying every case as holdout.
            root = subprocess.run(['git', '-C', str(pathlib.Path(__file__).resolve().parent),
                                   'rev-parse', '--show-toplevel'],
                                  capture_output=True, text=True, check=True).stdout.strip()
            out = subprocess.run(
                ['git', '-C', root, 'ls-tree', '--name-only', '-r', '-d',
                 TUNE_COMMIT, 'shadow-medic/cases/'],
                capture_output=True, text=True, check=True).stdout
            # Only entries that really are case dirs under cases/ count. Anything else (the two
            # parent dirs, or a './' degenerate answer) is discarded, so an empty result fails
            # closed to the ratchet rather than silently meaning "nothing is dev".
            names = set()
            for line in out.splitlines():
                parts = line.strip().rstrip('/').split('/')
                if len(parts) == 3 and parts[0] == 'shadow-medic' and parts[1] == 'cases' and parts[2]:
                    names.add(parts[2])
            _DEV_NAMES = names or False
        except Exception:
            _DEV_NAMES = False
    return _DEV_NAMES or None


def dev_case_names():
    """The dev set: the checked-in manifest, plus the tuning tree when history is reachable.

    The MANIFEST is the authority, because it is the only half that travels. Making the git tree
    a runtime prerequisite broke the copy-this-scaffold path the README sells: source archives,
    shallow clones and copied scaffolds have no 626de28, so every new case raised and the corpus
    stopped growing. The tree is now a cross-check (see --verify-manifest) rather than a gate.
    """
    names = set(manifest_names())
    tree = tree_case_names()
    if tree:
        names |= tree
    return names


def verify_manifest():
    """Cross-check the manifest against the tuning tree. Only meaningful where history exists."""
    tree = tree_case_names()
    if tree is None:
        print(f"tuning tree {TUNE_COMMIT!r} is not reachable here, nothing to cross-check")
        return 0
    man = manifest_names()
    missing = tree - man
    for n in sorted(missing):
        print(f"MISSING from {DEV_MANIFEST.name}: {n} (present in the tuning tree)")
    extra = man - tree
    for n in sorted(extra):
        print(f"manifest-only (deliberate --split dev after the baseline): {n}")
    print(f"manifest {len(man)}, tree {len(tree)}, missing {len(missing)}")
    return 1 if missing else 0


def split_for(name):
    """dev if the tuning tree holds this case, else holdout. Never demotes an existing dev case:
    if git is unreachable, an existing meta.json wins over the flag default."""
    if name in dev_case_names():
        return 'dev'
    prior = CASES / name / 'meta.json'
    if prior.exists():
        try:
            if json.loads(prior.read_text()).get('split') == 'dev':
                return 'dev'
        except Exception:
            pass
    # An explicit --split dev is a deliberate act and outranks the tree: the ratchet only ever
    # refuses to DEMOTE. Without this the flag was silently ignored whenever git answered, so a
    # deliberate tuning harvest would have written gate-eligible cases.
    if SPLIT == 'dev':
        return 'dev'
    # Not in the dev set and no prior meta claiming dev, so this case was never tuned on and
    # holdout is the truth rather than a guess. That holds because the manifest is checked in and
    # append-only: absence from it is real evidence, not a gap.
    #
    # One state is still genuinely unknown. A manifest that EXISTS but is EMPTY, with no reachable
    # tree, means a baseline was declared and then lost. Classifying then would silently move
    # already-seen cases into the gate, so refuse.
    if DEV_MANIFEST.exists() and not manifest_names() and tree_case_names() is None:
        raise SplitUnknown(
            f"cannot classify {name!r}: {DEV_MANIFEST.name} exists but is empty and tuning tree "
            f"{TUNE_COMMIT!r} is unreachable, so this repo declared a tuning baseline and then "
            "lost it. Restore the manifest or make the commit reachable.")
    return 'holdout'

def stage_script(stage):
    global SCRIPT_BY_STAGE
    if SCRIPT_BY_STAGE is None:
        SCRIPT_BY_STAGE = {}
        for line in (OUT_LOG / 'run.log').read_text(errors='ignore').splitlines():
            m = re.search(r'stage=(\S+) script=(\S+)', line)
            if m:
                SCRIPT_BY_STAGE[m.group(1)] = m.group(2)
    return SCRIPT_BY_STAGE.get(stage)

def _parse_stamp(line):
    """Stage logs carry one of three stamp shapes; a parser that knows only one silently
    yields empty evidence and the case is skipped as 'too thin' (measured 2026-08-29:
    half the ledger's events were unharvestable for exactly this reason)."""
    m = re.match(r'^[A-Z][a-z]{2} ([A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d) [A-Z]{3} (\d{4})', line)
    if m:
        try:
            return datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %d %H:%M:%S %Y")
        except ValueError:
            return None
    m = re.match(r'^(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)', line)          # ISO local
    if m:
        try:
            return datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if line.startswith('{'):                                                       # JSONL with a ts field
        m = re.search(r'"ts"\s*:\s*"(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)(Z?)', line)
        if m:
            try:
                ts = datetime.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
                if m.group(3) == 'Z':                                              # UTC -> local, matching the ctime lines
                    ts += datetime.datetime.now() - datetime.datetime.utcnow()
                return ts
            except ValueError:
                return None
    return None


def window(path, center, minutes=40, maxlines=45):
    """Lines of a dated log within [center-minutes, center+2min]."""
    stamped = []
    try:
        text = path.read_text(errors='ignore')
    except OSError:
        return ''
    for line in text.splitlines():
        ts = _parse_stamp(line)
        if ts:
            stamped.append((ts, line))
        elif stamped:
            stamped.append((stamped[-1][0], line))   # continuation line inherits prior stamp
    # PAST ONLY: the case must freeze what the incumbent could see at decision time. A window
    # that includes the future lets the shadow call a then-open fault 'already healed' from
    # evidence that did not exist yet (U-20260829T0129 taught this: GLM saw later green passes
    # inside a +-40min window and reasonably flipped JUDGMENT to MECHANICAL).
    lo, hi = center - datetime.timedelta(minutes=minutes), center + datetime.timedelta(minutes=2)
    out = [line for ts, line in stamped if lo <= ts <= hi]
    return "\n".join(out[-maxlines:])


# Exact multi-word phrases that read as names to the roster regex and are not. The first entry
# minted case S-20260830T0546's error text as a person and then refused the case against the
# template sentence that quotes the same error. 'Fired RUN' is the medic's own phrase for a re-fire
# ("Fired RUN stage=Q by=medic", seven ledger notes), minted as a person until 2026-10-17, which put
# "[person1] stage=Q" in the answer key and handed compare.py the surname RUN (see RUNNER_STATUS there).
NOT_NAMES = {'Exceeded USD', 'Budget limit', 'Fired RUN'}

# THE MEDIC'S EMPHASIS PHRASES ARE ITS GRAMMAR, NEVER A PERSON (2026-10-17). The medic writes ledger
# notes like "Claim RENEWED, not released", "Left RED" and "Stays RED pending a real green DONE", a
# capitalized word and then a word in capitals for emphasis. The roster regex read 98 such phrases in
# the ledger as names, so answer keys said "[person1], not released". A candidate is skipped as the
# medic's phrase only when it is exactly one of the two-word phrases in MEDIC_PHRASES, taken from the
# ledger as of 2026-10-17 the way the runner's status words come from run-stage.sh, or a case id the
# medic fixed or applied ("Fix M-" before "M-20260912T220806"). A rule built from separate lists of
# lead words and emphasis words skipped pairs the medic never wrote, and some were people ("Left HAND",
# "Evidence GREEN"), so only the exact phrases count (adversary, 2026-10-18). Any other pair, a longer
# capture ("Claim RENEWED GREEN"), a first name before an emphasis word ("Tavio DONE"), a name with an
# acronym ("Orvin CA RTR") and a company ("Quillfern AI") are minted as before. A phrase the medic
# starts writing later is minted until it is added here, the safe direction, and test_medic_phrases.py
# lists the ledger's phrases near the rule.
MEDIC_PHRASES = frozenset({
    'Also CORRECTED', 'Also NOT', 'Also VERIFIED', 'Also WITHDREW', 'Audit RAN', 'Blocker NOT', 'Blocker PROBED',
    'Body RECOMPACTED', 'Budget NOT', 'Ceiling NOT', 'Claim HELD', 'Claim RELEASED', 'Claim RENEWED', 'Claims HELD',
    'Classified TRANSIENT', 'Closed GREEN', 'Comet FELL', 'Condition NOT', 'Counting SEND', 'Deliberately NOT',
    'Detached XI', 'Evidence STOPS', 'Fired DETACHED', 'Fired ONE', 'Fired RUN', 'Found OUTSIDE', 'Gate NOT',
    'Kept RED', 'Left RED', 'Missing DONE', 'Newest COMPLETED', 'Original RCA', 'Posted ONE', 'Probed DNS',
    'Quoted DONE', 'Raising BUDGET', 'Row CLEARED', 'Ruled OUT', 'Scheduled RUN', 'Standing RCA', 'Stays RED',
    'Still AUTH', 'Still NOT', 'Verified ALIVE', 'Verified NO', 'Verified NOT',
    'Verified THREE', 'Verify FAILED', 'Verify NOT', 'Watch KILLED', 'Zero NEW'})
CASE_ID_LEADS = frozenset({'Fix', 'Applied'})


def medic_phrase(toks):
    """True when toks is one of the medic's own two-word phrases (see MEDIC_PHRASES)."""
    return len(toks) == 2 and (' '.join(toks) in MEDIC_PHRASES
                               or (toks[0] in CASE_ID_LEADS and re.fullmatch(r'[A-Z0-9]{1,5}-', toks[1]) is not None))


def promote(stage_dir, case, slug, roster):
    """Save the roster to the map store and move the staged case into place as one step. The roster
    holds real names, so it goes to the store outside the repo, never into the case folder (see
    compare.py), and it is saved before the case lands, so a case is never in cases/ without its map.
    If the move then fails, the old case folder and the map the store held before both come back, so
    an old case is never lost or left paired with a new roster (adversary, 2026-10-18)."""
    store = cmp_mod.map_path(slug)
    prior = store.read_text() if store.exists() else None
    old = case.with_name('.' + case.name + '.replaced') if case.exists() else None
    cmp_mod.save_map(slug, roster)
    try:
        if old is not None:
            if old.exists():
                shutil.rmtree(old)
            case.rename(old)
        case.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(stage_dir), str(case))
    except BaseException:
        if old is not None and old.exists():
            if case.exists():
                shutil.rmtree(case, ignore_errors=True)
            old.rename(case)
        if prior is None:
            store.unlink(missing_ok=True)
        else:
            cmp_mod.save_map(slug, json.loads(prior))
        raise
    if old is not None:
        shutil.rmtree(old, ignore_errors=True)


def build_roster(text):
    names = set()
    # A capitalized pair whose FIRST token is an English function word is never a person
    # ("No Slack ..." minted the roster entry 'No Slack', whose surname 'Slack' then blocked a
    # case at the preflight). Function words and product names are the two false-positive families.
    skip = {'Fri','Thu','Mon','Tue','Wed','Sat','Sun','Stage','Step','Nothing','Pending','Triage','One','The','Search','Sent','Received','Recommendation','Board','Parent','Diagnosis','Session','Judgment','Checked','Worker','Fleet','Health','Landed','Stage-Watch','Script','Exit','Ran','Dashboard','Logs','Claude','Code','Opus','Sonnet','Haiku','Fable','Slack','Gmail','Google','James',
            'No','Not','New','All','Any','Each','Every','Both','Two','Three','This','That','These','Those','Some','Only','After','Before','When','While','With','From','Into','Over','Under','Next','Last','First','Same','Since','Then','There','Here','Now','Yes','If','And','But','For','Its','Was','Has','Had','Did','Does','Will','Would','Should','Could','May','Might','Must','Can'}
    # Roster building stays OVER-INCLUSIVE on purpose (a refuting reviewer's finding, 2026-08-29): a filter here
    # can drop a REAL name ("Jane Smith" beside a lowercase "jane-smith") and then nothing ever
    # redacts it. Over-redaction is safe; a missed name is not. The vocabulary filter lives in
    # compare.py, applied only to the single tokens derived from the roster.
    # Build-time only, phrase-level only (adversary ruling 2026-08-29): a multi-word candidate is
    # skipped when it is a known false-positive phrase, or appears verbatim in the frozen doctrine
    # template. Single tokens are never filtered here and compare.py's derived-token checks are
    # untouched, because the template quotes James by name and a surname filter would have let a
    # standalone "James" through both redaction and detection.
    tmpl = (pathlib.Path(__file__).parent / 'prompt-template.md')
    tmpl_low = tmpl.read_text().lower() if tmpl.exists() else ''
    # A LEADING SKIP WORD IS PEELED OFF, NEVER A VERDICT ON THE WHOLE CAPTURE (2026-10-17). finditer
    # resumes after a match, so skipping "Sent Jane Smith" outright meant Jane Smith was never looked
    # at again, went out unredacted, and passed the check, which had no roster entry to look for.
    # The rest is captured afresh from its first name-shaped word that is not a skip word, so a run of
    # skip words cannot use up the capture's four tokens before the name ("Then From With Jane Smith",
    # "Then RUN Jane Smith"), and it is judged like any other candidate, so it still needs two tokens.
    # A skip word that is also a given name ("Will", "May") can BE the first name, so when a name-shaped
    # word follows it the whole capture is minted too ("Will Smith"), while "Will NOT" is not.
    cap = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)?(?: [A-Z][a-zA-Z'-]+){1,3})\b")
    name_start = re.compile(r"[A-Z][a-z]+(?:[A-Z][a-z]+)?$")
    given_skips = {'Will', 'May'}
    known = lambda n: n in NOT_NAMES or (tmpl_low and ' ' in n and n.lower() in tmpl_low)
    for m in cap.finditer(text):
        toks = m.group(1).split()
        if toks[0] in skip:
            pos, i = m.start(1), 0
            while i < len(toks) and (toks[i] in skip or not name_start.match(toks[i])):
                # Wherever it sits in the run ("Will Smith", "Sent Will Smith"), a given-name skip word
                # with a name-shaped word after it starts a candidate of its own.
                if toks[i] in given_skips and i + 1 < len(toks) and name_start.match(toks[i + 1]):
                    m3 = cap.match(text, pos)
                    if m3 and not known(m3.group(1)) and not medic_phrase(m3.group(1).split()):
                        names.add(m3.group(1))
                pos, i = pos + len(toks[i]) + 1, i + 1
            m2 = cap.match(text, pos) if i < len(toks) else None
            if not m2:
                continue
            toks = m2.group(1).split()
        if len(toks) < 2 or not name_start.match(toks[0]):
            continue
        n = ' '.join(toks)
        if known(n) or medic_phrase(toks):
            continue
        names.add(n)
    for m in re.finditer(r'\b([a-z]{3,} [a-z]{3,})\b \(\d+/', text):
        names.add(m.group(1))
    return {n: f'[person{i+1}]' for i, n in enumerate(sorted(names, key=len, reverse=True))}

def events(limit):
    rows = [json.loads(l) for l in open(LEDGER) if l.strip()]
    seen, out = set(), []
    for r in rows:
        stage, act, note = r.get('stage'), r.get('action'), (r.get('note') or '')
        if stage in SKIP_STAGES or act not in CLASS_BY_ACTION or len(note) < 200:
            continue
        if 'REVISIT' in note[:60]:
            continue
        # One fault can leave several ledger rows: a MIRROR row for the Stage-Watch alert (the launcher's
        # own red about a failed stage) beside the primary row for the stage's own red, 'SAME single fault',
        # 'one fire serves both'). Only the primary is a case; a mirror carries another stage's evidence
        # and produced the N-20260823T1151 artifact (GLM rightly said it had nothing to cite).
        if re.search(r'\bmirror\b|SAME (?:single )?fault|one fire serves both', note[:600], re.I):
            continue
        day = (r.get('at') or '')[:10]
        key = (stage, day)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[-limit:]

def main():
    global SPLIT
    known = {'--dry-run', '--verify-manifest', '--split', '--limit', '--new-only'}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a not in known:
            sys.exit(f"harvest: unknown argument {a!r}. Flags: {' '.join(sorted(known))}. "
                     "A bare `harvest.py` runs the full sweep; nothing else is inferred.")
        i += 2 if a in ('--split', '--limit') else 1
    limit = 60; dry = '--dry-run' in sys.argv; new_only = '--new-only' in sys.argv
    if '--verify-manifest' in sys.argv:
        sys.exit(verify_manifest())
    if '--split' in sys.argv:
        SPLIT = sys.argv[sys.argv.index('--split') + 1]
        # Validate at the door. split_for() tests `SPLIT == 'dev'` exactly and treats anything
        # else as holdout, so a typo like --split deev would have silently written a case the
        # operator meant to tune on straight into the promotion gate. An unknown split is an
        # operator error, never a default.
        if SPLIT not in ('dev', 'holdout'):
            sys.exit(f"harvest: --split must be 'dev' or 'holdout', got {SPLIT!r}")
    if '--limit' in sys.argv:
        limit = int(sys.argv[sys.argv.index('--limit') + 1])
    made = skipped = 0
    for r in events(limit):
        stage = r['stage']; at = r['at']
        center = datetime.datetime.fromisoformat(at).astimezone().replace(tzinfo=None)
        slug = f"{stage}-{at[:16].replace(':','').replace('-','')}"
        case = CASES / slug
        if new_only and case.exists():
            continue
        script = stage_script(stage)
        runlog = window(OUT_LOG / 'run.log', center)
        stagelog = window(OUT_LOG / f"{script.replace('.sh','')}.log", center) if script else ''
        # run.log is rotated and only reaches back ~6 days (measured 2026-08-29: earliest Aug 23),
        # so older events have stage-log evidence only. That is a HARDER case, not an invalid one:
        # the stage's own log carries its error and exit line. Say plainly that runner evidence is
        # absent so the shadow never invents a PERM/DONE line it cannot see.
        if len(stagelog) < 200 or (not runlog and len(stagelog) < 800):
            print(f"skip {slug}: evidence too thin (runlog {len(runlog)}b, stagelog {len(stagelog)}b)")
            skipped += 1
            continue
        runlog_present = bool(runlog)
        if not runlog:
            runlog = "(run.log does not reach this date; no runner evidence is available for this case. "
            runlog += "Diagnose from the stage log alone and say so.)"

        code = ''
        if script:
            errline = re.search(r'([A-Za-z ]{6,60}?(?:FAILED|error|ERROR|failed)[^\n]{0,40})', stagelog)
            if errline:
                pat = re.escape(errline.group(1).strip()[:40])
                g = subprocess.run(['grep','-n','-B4','-A10','-E',pat,str(FLEET/'scripts'/script)],capture_output=True,text=True)
                code = g.stdout[:6000]
        kclass = ledger_class(r.get('note'), r['action'])
        roster = build_roster(runlog + "\n" + stagelog + "\n" + r.get('note',''))
        if dry:
            # Resolve the split HERE too. Dry-run used to return before split_for() ever ran, so
            # the "--dry-run first, always" the README advertises could pass clean while the real
            # harvest died on provenance. A rehearsal that skips the step that fails is not one.
            print(f"would make {slug}: class={kclass} split={split_for(slug)} roster={len(roster)} "
                  f"runlog={len(runlog)}b stagelog={len(stagelog)}b code={len(code)}b")
            continue
        # STAGE THEN PROMOTE (a refuting reviewer's finding, 2026-08-29): raw production evidence must
        # never touch the committable tree. Build and redact in a temp dir OUTSIDE the repo;
        # only a case that passes the leak check is moved into cases/. A crash mid-harvest
        # strands nothing but a tmpdir the OS owns.
        stage_dir = pathlib.Path(tempfile.mkdtemp(prefix=f'shadow-harvest-{slug}-'))
        try:
            (stage_dir/'input-runlog.txt').write_text(runlog)
            (stage_dir/'input-qlog.txt').write_text(stagelog)
            (stage_dir/'input-code.txt').write_text(code or '(no code excerpt for this case)')
            (stage_dir/'answer-key.md').write_text(
                f"# Answer key (from the production medic's ledger)\n\nClass: {kclass}\n\nLedger note (verbatim, redacted):\n- {at[11:19]} {r['action']} | {r.get('note','')}\n")
            # split: cases minted before the 2026-08-29 instrument/doctrine tune are the DEV set
            # (they were seen while fixing the harness). Everything minted after is HOLDOUT and is
            # the only thing the promotion gate may read (temporal-split discipline, research
            # 2026-08-29: a set used for tuning is spent after a handful of iterations).
            case_split = split_for(slug)
            json.dump({'stage': stage, 'script': script or '',
                       'log': (script.replace('.sh','') + '.log') if script else '',
                       'split': case_split, 'runner_evidence': bool(runlog_present)},
                      open(stage_dir/'meta.json','w'), indent=1)
            for f in ('input-runlog.txt','input-qlog.txt','input-code.txt','answer-key.md'):
                q = stage_dir/f
                q.write_text(cmp_mod.redact_text(q.read_text(), roster))
            rc = cmp_mod.cmd_check(stage_dir, [], mp=roster)
            if rc:
                print(f"skip {slug}: leak check failed after redaction; nothing promoted")
                skipped += 1
                continue
            promote(stage_dir, case, slug, roster)
            stage_dir = None
            # The case is on disk and past the leak check, so its provenance is now a fact worth
            # recording. Anything earlier would have been a promise.
            if case_split == 'dev':
                remember_dev(slug)
        finally:
            if stage_dir is not None:
                shutil.rmtree(stage_dir, ignore_errors=True)
        made += 1
        print(f"made {slug}: class={kclass}")
    print(f"harvest: {made} case(s) made, {skipped} skipped")

if __name__ == '__main__':
    main()
