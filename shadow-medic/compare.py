#!/usr/bin/env python3
"""compare.py: redaction, leak checks and scoring for shadow-medic.

shadow-medic is this folder's harness that replays the medic's diagnoses against a challenger model.
The medic is the automated worker that diagnoses red alerts from the fleet, the scheduled jobs in
claude-os (the private repo of automation stages this harness studies), and its ledger is the log of
every action it took. Each job is a stage, named by a letter or Roman numeral (K, Q, XVII), and its
script and log carry that id (K-cswap-auto.sh, K-cswap-auto.log). run-stage.sh, the runner that starts
every stage, writes one line per run to run.log. A case is one past alert frozen as files: the run.log
window around it, the stage's own log, a code excerpt, and the medic's note as the answer key.
harvest.py builds the cases. A case's roster is the list of names harvest found in its text, each
mapped to a placeholder such as [person1]. This file redacts a case against its roster, checks every
file and the built prompt for anything left (the preflight run-shadow.sh runs before a prompt leaves the
machine), and scores the challenger against the answer keys. A comment that cites the adversary marks
a hole an adversarial reviewer found and the fix that closed it.

  compare.py compare <case-dir> <results...>    each shadow verdict beside the answer key; exit 1 on any miss or missing verdict
  compare.py check   [--structural-only] <case-dir> [more files...]
                                                 redaction preflight over the case inputs, answer key and any extra files;
                                                 exit 1 on any leak (roster tokens when the case's map is in the store, plus
                                                 structural patterns), and refused outright when the map store is missing,
                                                 unless --structural-only asks for the structural patterns alone (CI)
  compare.py redact  <map.json> <files...>       rewrite files in place: structural patterns, full names, every single roster token, roster-derived slugs
  compare.py migrate-maps [cases-dir]            move every roster map out of the case folders into the map store outside the repo
                                                 (~/.shadow-os/redaction-maps, or $SHADOW_MAP_DIR), one <case>.json each
  compare.py scoreboard [--model glm-5.3] [--engine zai] [--p0 0.80] [--p1 0.92] [--split holdout|dev|all] [--family ops|render|all]
                                                 corpus-wide agreement: latest result per case, Wilson 95% interval, and a
                                                 pre-registered SPRT (H0: agreement <= p0, H1: >= p1, alpha=beta=0.05) that
                                                 says PROMOTE, REJECT, or CONTINUE as cases accumulate one at a time
"""
import contextlib, os, re, sys, json, pathlib, tempfile

STRUCT = [
    (r'[\w.+-]+@[\w-]+\.[\w.]+', 'email'),
    (r'linkedin\.com/in/[^\s)"\']+', 'linkedin url'),
    (r'\b[DUBC]0[A-Z0-9]{8,}\b', 'slack id'),
    (r'\b1[5-9]\d{8}\.\d{3,}\b', 'slack ts'),
    (r'\b[a-z]+(?:-[a-z]+)*-\d{5,}\b', 'profile slug'),
    (r'\(\d{3}\)\s?\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b', 'phone'),
]
COMMON = {'goes', 'lee', 'hope', 'lincoln', 'reed', 'may', 'march', 'will', 'grant', 'art', 'young', 'long', 'white', 'black', 'green', 'brown', 'king', 'hill', 'wood', 'stone', 'price', 'bell', 'best', 'love', 'day', 'ray', 'ward', 'gray', 'moon', 'star'}

# THE RUNNER'S STATUS SLOT IS ITS GRAMMAR, NEVER A PERSON (2026-10-17). run-stage.sh writes every
# run.log line as `<date>: RUN stage=K ...`, and the medic's ledger says "Fired RUN stage=Q by=medic".
# harvest's roster regex read that phrase as a name, its derived surname RUN was redacted with re.I,
# and every RUN line in two holdout cases' run.log windows became "[surname] stage=", 34 lines of the
# evidence the shadow reads. So the surname and first-name passes never rewrite a runner status word
# IN ITS OWN SLOT, meaning a line that starts with run.log's timestamp, then a status run-stage.sh
# prints (a word, or one of its two ALERT phrases), then " stage=" and a stage id the runner prints
# (K, XVII, 7). The whole status must be in the set, so a name in capitals before or after a runner
# word ("SMITH RUN", "ALERT SMITH") makes no slot. Anywhere else the same word
# redacts exactly as before, so a real surname that spells a status word is still caught, and a forged
# slot holding any other word, or no runner stage id, protects nothing. The set is fixed on purpose.
# Learning words from the scanned text let one forged line exempt a real surname for the whole file,
# and a bare " stage=" let a stage-log field like "stage=applicant" pass (adversary, 2026-10-17). The
# phrase pass is untouched, so a whole roster name redacts everywhere. A word the runner learns later
# is over-redacted until it is added here, the safe direction, and test_roster_status_words.py fails
# when run-stage.sh prints a word this set lacks.
RUNNER_STATUS = frozenset({'AUTH', 'CAP', 'DEFERRED', 'DONE', 'DRILL', 'FATAL', 'HANDOFF', 'HEALTHWRITE', 'IDLE', 'KILLED',
                           'NETWORK', 'PERM', 'QUOTA', 'RATELIMIT', 'RETRY', 'RUN', 'SKIP', 'STOPPED', 'WARN',
                           'ALERT HELD', 'ALERT DUPLICATE SUPPRESSED'})
_RUNNER_SLOT = re.compile(r'^[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} [A-Z]{2,5} \d{4}: ([A-Z]+(?: [A-Z]+)*)'
                          r'(?= stage=[A-Z0-9]{1,5}(?:\s|$))', re.M)


def _runner_slots(t):
    """Spans of each runner status word sitting in its own run.log slot."""
    return [m.span(1) for m in _RUNNER_SLOT.finditer(t) if m.group(1) in RUNNER_STATUS]


_PLACEHOLDER = re.compile(r'\[(?:person\d+|surname|first|slug|redacted)\]')
# THE COMMAND-LINE FLAGS THE STAGE LOGS CARRY ARE TEXT, NEVER A NAME (2026-10-18). The medic passes
# the max-budget-usd flag on every call, and a roster holding a person named Max put a [first] into
# it. A name pass never rewrites one of these exact flags, taken from the live stage logs on
# 2026-10-18 the way the runner's status words come from run-stage.sh: max-budget-usd from
# H-ping-heal.log, run.log and four other stage logs, curl's max-time from F-aj-holoblack.log, and
# max-ply from one more stage's log. Only the whole flag is protected, and only when it ends there (a
# letter, digit, hyphen, apostrophe, or a dot, colon or slash running on into more text makes it a
# longer token), so "max approved" about a person, or a longer or different flag, redacts as before.
# A flag whose parts hold two tokens of one roster name is not protected either, so a roster that
# names a person the way a flag is spelled still redacts it (adversary, 2026-10-18).
# test_redaction_names.py fails when a stage log carries a max flag this set lacks.
CLI_FLAGS = frozenset({'--max-budget-usd', '--max-time', '--max-ply'})
_CLI_FLAG = re.compile(r"(?<![\w-])-{2}max-[a-z0-9]+(?:-[a-z0-9]+)*(?![\w'\u2019-]|[.:/]\w)")
# THE RUNNER'S OWN STAGE FILES ARE A FIXED SET (2026-10-18). Each stage script in run-stage.sh's stage
# table and the log it writes, ${SCRIPT%.sh}.log, the fleet's identifiers in run.log's script= field, in
# stage logs and in the two labels meta.json puts into every built prompt. A name pass must not turn
# K-cswap-auto.sh into K-[surname]-auto.sh because an over-inclusive roster holds "Cswap". Only these
# exact names are protected. Any other file name of the same shape is ordinary text, so a name run into
# one ("X-janesmith.sh") or written as its prefix ("SMITH-notes.py") redacts as it would anywhere else,
# which a rule keyed on the shape alone let through (adversary, 2026-10-18). A stage added to
# run-stage.sh is over-redacted until it is added here, the safe direction, and test_redaction_names.py
# fails when the two differ. This public copy lists only the jobs named in its published incidents, so
# that drift check runs only when SHADOW_RUNNER points at a fleet runner.
STAGE_FILES = frozenset({'1-log', '2-distill', '3-promote', '4-sync-confluence', '5-sync-notion', '6-gc', '7-deploy',
                         'A-twin-harvest', 'B-twin-retrain', 'C-twin-gc', 'D-aj-brief', 'E-aj-hologram',
                         'F-aj-holoblack', 'G-drive-backup', 'H-ping-heal', 'I-model-watch',
                         'II-confluence-to-notion', 'IV-laws-refresh', 'IX-permission-cleanup', 'J-live-suites',
                         'K-cswap-auto', 'P-promo-purge', 'V-fiscal-policy',
                         'VI-monetary-policy', 'VII-mint-intake', 'VIII-shock-drill',
                         'X-release-watch', 'XI-navigator-refresh', 'XII-model-promote', 'XIII-shadow-train',
                         'XIV-route-learn', 'XIX-opto-morning', 'XV-browser-memory', 'XVI-fallback-canary',
                         'XVII-macpro-door', 'XVIII-apprentice', 'Y-dm-mute', 'Z-blocked-trash'})
# The name must end there, so K-cswap-auto.sh.bak, K-cswap-auto.log-old or a name written straight
# after one (K-cswap-auto.sh'ara) is ordinary text, while a sentence's closing period after it ("ran
# K-cswap-auto.sh.") still ends the name.
_STAGE_FILE = re.compile(r"(?<![\w.-])([A-Z0-9]{1,5}-[a-z0-9]+(?:-[a-z0-9]+)*)\.(?:sh|log)(?![\w'\u2019-]|\.\w)")
# Any word or compound joined by hyphens or underscores, in any casing. The slug pass lowercases it
# before asking whether it holds a name, so "JANESMITH" is read like "janesmith", and an underscore
# joins parts like a hyphen, so "jane_smith" is read like "jane-smith" (adversary, 2026-10-18).
_SLUG = re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9])')


def _entries(mp):
    """Each roster name as the set of its lowercase parts of three letters or more, possessive off, a
    hyphenated token split into its parts ("Zor-Vin" is zor and vin) the way _holds_a_name splits a slug."""
    return [{x for t in re.split(r'\s+', n) for x in re.split(r'[^a-z0-9]+', _POSSESSIVE.sub('', t).lower()) if len(x) >= 3}
            for n in mp]


def _holds_a_name(s, entries):
    """True when s carries two tokens of one roster name ("jane-smith", "X-jane-smith.sh")."""
    parts = set(re.split(r'[^a-z0-9]+', s.lower()))
    return any(len(e & parts) >= 2 for e in entries)


def _protected(t, entries=()):
    """Spans no name pass touches, each runner status slot, each of the runner's own stage file names,
    each command-line flag in CLI_FLAGS, and each placeholder this module already wrote, so a roster
    token spelled "first" cannot eat "[first]", a roster token "Cswap" cannot turn K-cswap-auto.sh into
    K-[surname]-auto.sh, and a roster holding Max cannot rewrite the max-budget-usd flag."""
    return (_runner_slots(t)
            + [m.span() for m in _STAGE_FILE.finditer(t) if m.group(1) in STAGE_FILES]
            + [m.span() for m in _CLI_FLAG.finditer(t) if m.group(0) in CLI_FLAGS and not _holds_a_name(m.group(0), entries)]
            + [m.span() for m in _PLACEHOLDER.finditer(t)])


def _inside(m, spans):
    """True when the match lies wholly inside one protected span. A match that only overlaps one runs
    into text the span does not cover, so it is never shielded: a surname written straight after a
    stage file's .sh ("K-cswap-auto.sh'ara") once hid behind the file name (adversary, 2026-10-18)."""
    return any(a <= m.start() and m.end() <= b for a, b in spans)


def _outside_slots(pattern, t, flags=0, entries=()):
    """Matches of pattern in t, minus any lying wholly inside a protected span."""
    spans = _protected(t, entries)
    return [m for m in re.finditer(pattern, t, flags) if not _inside(m, spans)]


def _sub_outside_slots(pattern, repl, t, flags=0, entries=()):
    """re.sub with a literal replacement that leaves a match lying wholly inside a protected span as it
    was. One that runs past a span's edge is replaced whole, the safe direction."""
    spans = _protected(t, entries)
    return re.sub(pattern, lambda m: m.group(0) if _inside(m, spans) else repl, t, flags=flags)


# THE ROSTER MAPS LIVE OUTSIDE THE REPO (2026-10-18). A case's map is the one file in it that holds
# real names, and a gitignored file is still a file every tool run inside the repo can read, an
# adversarial reviewer's included. So each map lives in the map store as <case name>.json, by default
# ~/.shadow-os/redaction-maps or wherever SHADOW_MAP_DIR points (an absolute path; the tests use a temp
# dir), owner-only. A store or a map file that resolves inside this repo is refused for reading and
# writing alike. A map still sitting in a case folder is refused at load, never skipped, and so is a
# case with no map in the store, so no case passes the check on structure alone because its roster
# was not found; `compare.py migrate-maps` moves the old maps and records an empty one for a case that
# never had any. The old shared map beside this file is no longer read.
REPO = pathlib.Path(__file__).resolve().parent.parent
LEGACY_MAP = 'redaction-map.local.json'


class MapInRepo(ValueError):
    """A roster map inside the repo: in a case folder, or through a store or link that resolves there."""


def _in_repo(p):
    rp, rr = os.path.realpath(p), os.path.realpath(REPO)
    return rp == rr or rp.startswith(rr + os.sep)


def map_dir():
    """The map store, refused when SHADOW_MAP_DIR is relative (it would move with the working
    directory) or when it resolves inside the repo."""
    raw = os.environ.get('SHADOW_MAP_DIR')
    d = pathlib.Path(raw).expanduser() if raw else pathlib.Path.home() / '.shadow-os' / 'redaction-maps'
    if not d.is_absolute():
        raise ValueError(f'SHADOW_MAP_DIR must be an absolute path, not {raw!r}')
    if _in_repo(d):
        raise MapInRepo(f'the map store {d} resolves inside the repo')
    return d


def map_path(name):
    """The store path of a case's map. A name that is not a plain case folder name is refused, and so
    is a map file that resolves inside the repo through a link planted in the store."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', name or ''):
        raise ValueError(f'not a case name: {name!r}')
    p = map_dir() / (name + '.json')
    if _in_repo(p):
        raise MapInRepo(f'the map {p} resolves inside the repo')
    return p


def save_map(name, mp):
    """Write a case's roster to the store, owner-only. It goes to a fresh temp file no planted link can
    redirect, is synced, and is renamed over the map, which replaces a link rather than writing through it."""
    p = map_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(p.parent, 0o700)
    p = map_path(name)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix='.' + p.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as fh:
            json.dump(mp, fh, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    dfd = os.open(p.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return p


def load_map(case):
    """The case's roster from the map store, or None when the store holds no map for it. A map left in
    the case folder raises MapInRepo instead of being read or skipped."""
    case = pathlib.Path(case)
    if (case / LEGACY_MAP).exists():
        raise MapInRepo(f'{case / LEGACY_MAP} is a roster map inside the case folder; run `compare.py migrate-maps`')
    p = map_path(case.name)
    return json.load(open(p)) if p.exists() else None


def cmd_migrate_maps(cases_dir=None):
    """Move every roster map out of the case folders into the map store. A store map with other content
    is never overwritten: that case is reported and both copies are left as they are."""
    root = pathlib.Path(cases_dir) if cases_dir else pathlib.Path(__file__).parent / 'cases'
    moved = bad = 0
    for legacy in sorted(root.glob('*/' + LEGACY_MAP)):
        name, mp = legacy.parent.name, json.load(open(legacy))
        dest = map_path(name)
        if dest.exists() and json.load(open(dest)) != mp:
            print(f"CONFLICT {name}: the store already holds a different map; both left as they are")
            bad += 1
            continue
        save_map(name, mp)
        if json.load(open(dest)) != mp:
            print(f"FAILED {name}: the stored copy does not read back the same; the case folder keeps its map")
            bad += 1
            continue
        legacy.unlink()
        moved += 1
    empty = 0
    for case in sorted(p for p in root.iterdir() if p.is_dir() and (p / 'answer-key.md').exists()):
        if not (case / LEGACY_MAP).exists() and not map_path(case.name).exists():
            save_map(case.name, {})
            print(f"EMPTY {case.name}: no roster was ever recorded, so an empty one is stored and the case is checked on structure, as before")
            empty += 1
    print(f"migrate-maps: {moved} moved to {map_dir()}, {empty} recorded empty, {bad} left in place")
    return 1 if bad else 0


# Two-letter tokens that are words and never a name. Every other two-letter Title-case token in a
# roster name ("Li", "Wu", "Ng", "He") is a name part, matched only as written or in capitals.
_NOT_SHORT_NAMES = frozenset({'Am', 'An', 'As', 'At', 'Be', 'By', 'Co', 'Dr', 'Go', 'Hi', 'If', 'In', 'Is', 'It', 'Jr', 'Me',
                              'Mr', 'Ms', 'My', 'No', 'Of', 'Oh', 'Ok', 'On', 'Or', 'Re', 'So', 'Sr', 'St', 'To', 'Up', 'Us',
                              'Vs', 'We'})
_POSSESSIVE = re.compile(r"['’]s?$")


def name_parts(mp):
    """The single tokens of every roster name (2026-10-17). firsts are first tokens, surnames every
    later token, middle names included, which used to be skipped, and shorts the two-letter tokens a
    name can carry, which used to be dropped, so "Li replied" went out beside a redacted "Li Wang". A
    token carrying a possessive is kept as written, which still covers "smith's", and its bare form
    joins it ("Smith's" is also Smith), so a later standalone "Smith" redacts too."""
    firsts, surnames, shorts = set(), set(), set()
    for n in mp:
        raw = [t for t in re.split(r'\s+', n) if t]
        bare = [_POSSESSIVE.sub('', t) for t in raw]
        parts = [(t, b) for t, b in zip(raw, bare) if len(t) >= 3]
        for i, (t, b) in enumerate(parts):
            group = firsts if i == 0 else surnames
            group.add(t)
            if b != t and len(b) >= 3:
                group.add(b)
        shorts.update(b for b in bare if re.fullmatch(r'[A-Z][a-z]', b) and b not in _NOT_SHORT_NAMES)
    return firsts, surnames, shorts


def _words(text):
    """Lowercase words standing alone in the text, outside the placeholders this module writes, so a
    "[person1]" cannot make a roster token spelled Person a word (adversary, 2026-10-18). A hyphenated
    slug counts as one word, so a name inside "jane-smith" does not make that name a word."""
    return set(re.findall(r'(?<![A-Za-z])[a-z][a-z-]{2,}(?![A-Za-z])', _PLACEHOLDER.sub(' ', text)))


_dict_cache = []


def _dictionary():
    """The system word list, lowercase entries only, or an empty set where there is none (a CI runner).
    The same common-word oracle claude-os's pii-patterns.sh uses for its roster: a name absent from it
    is distinctive enough to redact in lowercase, one present (ward, price, robin) is left alone there."""
    if not _dict_cache:
        try:
            with open('/usr/share/dict/words', errors='ignore') as fh:
                _dict_cache.append(frozenset(w.strip() for w in fh if w.strip().islower()))
        except OSError:
            _dict_cache.append(frozenset())
    return _dict_cache[0]


def _in_dictionary(w, d):
    """w, or a regular inflection of a word in d ("replies" is reply, "slotted" is slot)."""
    bases = [w]
    if w.endswith(('ies', 'ied')):
        bases.append(w[:-3] + 'y')
    if w.endswith('es'):
        bases.append(w[:-2])
    if w.endswith('s'):
        bases.append(w[:-1])
    if w.endswith('ed'):
        bases += [w[:-2], w[:-1]] + ([w[:-3]] if len(w) > 4 and w[-3] == w[-4] else [])
    if w.endswith('ing'):
        bases += [w[:-3], w[:-3] + 'e'] + ([w[:-4]] if len(w) > 5 and w[-4] == w[-5] else [])
    return any(b in d for b in bases)


def _name_pattern(tok, word, first):
    """The pattern for one roster token. It matches in every casing, except that a token which is a word
    (a COMMON English word, or one the word list knows) spares its all-lowercase spelling, which is the
    word. "Frost", "FROST" and "fRoSt" redact, "the frost" does not. A first name keeps its old reach into
    a CamelCase handle ("JaneProfile") in Title case or as given, a lowercase spelling included when the
    token is not a word ("orvinProfile"), while every other casing must end at a non-letter, so "MARCH"
    does not match inside "MARCHED"."""
    near = {tok[:1].upper() + tok[1:].lower()} | ({tok} if tok != tok.lower() or not word else set())
    near_rx = '(?:' + '|'.join(re.escape(f) for f in sorted(near, key=len, reverse=True)) + ')'
    far = ('(?!' + re.escape(tok.lower()) + '(?![A-Za-z]))' if word else '') + '(?i:' + re.escape(tok) + ')'
    if first:
        return r'(?<![A-Za-z])(?:' + near_rx + r'(?![a-z])|' + far + r'(?![A-Za-z]))'
    # A letter or digit on either side ends the match, never an underscore, so "lee_SMITH" redacts.
    return r'(?<![A-Za-z0-9])(?:' + near_rx + '|' + far + r')(?![A-Za-z0-9])'


def _token_patterns(text, mp):
    """(label, token, pattern, placeholder) for every single roster token, plus the stems the slug pass
    looks for. redact_text and leaks both build theirs here, so they cannot disagree on what a name is.

    A NAME THAT IS ALSO A WORD IS NARROWED, NEVER DROPPED (2026-10-17). The old filter dropped any token
    that appeared lowercase anywhere in the text, or inside a lowercase slug, so "Held" beside the verb
    "held" was never redacted in any casing, and "jane-smith" was hidden by the very slug it sat in. The
    filter existed so the doctrine template's prose could not block a case at the preflight. That is
    now handled where it arises, in cmd_check, which holds the template's fixed text to whole names and
    structure only. Here a word-like token still redacts in every casing a name is written in."""
    firsts, surnames, shorts = name_parts(mp)
    words, dictionary = _words(text), _dictionary()
    # Whether a token is a word decides only its LOWERCASE spelling, and only the system word list
    # answers it. Where there is none (a CI runner) only COMMON counts, so every other token redacts in
    # lowercase too, the safe direction. The text itself is never asked, because a name written in
    # lowercase there would make itself a word (adversary, 2026-10-17).
    def isword(x):
        w = x.lower()
        return w in COMMON or (bool(dictionary) and _in_dictionary(w, dictionary))
    # A token found only in all-lowercase roster entries, which harvest mints from "word word (3/"
    # shapes, has no capitalized spelling to go on. It stays out only when it is a word twice over, in
    # the word list and in this text ("this", "stage"), and otherwise matches in every casing. The
    # text alone used to decide, so a name such an entry holds, written once on its own in lowercase,
    # made itself a word and went out in every casing (adversary, 2026-10-18). Only the system word
    # list counts here, never COMMON: COMMON lists words that are also names (max, lee, may), and an
    # entry written all in lowercase gives no capital to tell the person from the word (adversary,
    # 2026-10-18).
    capped = {v for n in mp if n != n.lower() for t in re.split(r'\s+', n) for v in (t, _POSSESSIVE.sub('', t))}
    inlist = lambda x: bool(dictionary) and _in_dictionary(x.lower(), dictionary)
    keep = lambda x: x in capped or not (x.lower() in words and inlist(x))
    word = lambda x: x in capped and isword(x)
    pats = [('surname', s, _name_pattern(s, word(s), False), '[surname]')
            for s in sorted(surnames, key=len, reverse=True) if keep(s)]
    pats += [('first name', f, _name_pattern(f, word(f), True), '[first]')
             for f in sorted(firsts, key=len, reverse=True) if keep(f)]
    # A two-letter name redacts in every casing but lowercase, where "li" or "he" is too often a word.
    pats += [('short name', s, r'(?<![A-Za-z0-9])(?!' + re.escape(s.lower()) + r'(?![A-Za-z0-9]))(?i:' + re.escape(s) + r')(?![A-Za-z0-9])',
              '[first]')
             for s in sorted(shorts)]
    # Run-together names, whatever the text holds, so "janesmith" redacts even in a file that also says
    # "jane". Across roster names, every token of four letters or more is a stem, and a two-letter name
    # joins a stem but never another two-letter name ("liwang"). Within one roster name, any two or more
    # of its tokens of two letters or more, a two-letter word aside ("amylee", "liwu", "janealicesmith").
    stems = frozenset(x.lower() for x in firsts | surnames if len(x) >= 4)
    small = frozenset(s.lower() for s in shorts)
    groups = []
    for n in mp:
        g = frozenset(b for b in (_POSSESSIVE.sub('', t).lower() for t in n.split())
                      if len(b) >= 3 or (re.fullmatch(r'[a-z]{2}', b) and b.title() not in _NOT_SHORT_NAMES))
        if len(g) >= 1:
            groups.append(g)
    every = stems | small | frozenset().union(*groups)
    lead = re.compile('|'.join(re.escape(x) for x in sorted(every, key=len, reverse=True))) if every else None
    return pats, (stems, small, groups, lead), _entries(mp)


def _spells(p, g, stems=None):
    """True when p is two or more tokens of g with nothing between them, at least one of them in stems
    when stems is given. Worked forward over the positions of p, so no length of p can exhaust the stack."""
    states = {0: {(0, False)}}
    for i in range(len(p)):
        for n, has in states.get(i, ()):
            for x in g:
                if p.startswith(x, i):
                    states.setdefault(i + len(x), set()).add((min(n + 1, 2), has or (stems is not None and x in stems)))
    return any(n == 2 and (stems is None or has) for n, has in states.get(len(p), ()))


def _run_together(p, runs):
    """True when p is roster tokens with nothing between them, by the rules in _token_patterns."""
    stems, small, groups, lead = runs
    if lead is None or not lead.match(p):
        return False
    return _spells(p, stems | small, stems) or any(_spells(p, g) for g in groups)


def _is_slug(s, runs, entries):
    """A slug (lowercased by the caller) is a name when it carries two tokens of one roster name
    ("jane-smith", "jane-smith-a1b2c3"), or holds two roster tokens run straight together
    ("janesmith", "x-janesmith", "liwang"). One token inside a compound ("notion-token",
    "claim-released") is left to the token passes, which redact a name part there in every casing a name
    can take."""
    return (_holds_a_name(s, entries) or _run_together(s, runs)
            or any(_run_together(p, runs) for p in re.split(r'[-_]', s)))


def redact_text(t, mp):
    # Every structural pattern leaks() checks is one this removes, phones included, and it runs first,
    # so an address goes whole before a name pass can split it ("jane.smith@x.io" would otherwise keep
    # its domain beside "[first].[surname]").
    for pat, _ in STRUCT:
        t = re.sub(pat, '[redacted]', t)
    for n, p in sorted(mp.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(re.escape(n), p, t, flags=re.I)
    # The slug pass runs before the token passes, so a compound holding a name goes whole. Run after
    # them, a token pass could take one part first ("JaneSmith" to "[first]Smith", "jane-quenneville"
    # to "jane-[surname]") and leave the slug pass nothing to recognize.
    # Both passes repeat until nothing changes, so a part one pass exposes is taken by the next
    # ("TavioKhan" to "[first]Khan" to "[first][surname]", "[first]DalqBorin" to "[first][slug]"),
    # which leaks() would otherwise flag in the output.
    pats, runs, entries = _token_patterns(t, mp)
    for _ in range(4):
        before = t
        spans = _protected(t, entries)
        t = _SLUG.sub(lambda m: '[slug]' if not _inside(m, spans) and _is_slug(m.group(0).lower(), runs, entries) else m.group(0), t)
        for _, _, pat, placeholder in pats:
            t = _sub_outside_slots(pat, placeholder, t, entries=entries)
        if t == before:
            break
    return t


NAME_KINDS = ('surname', 'first name', 'short name', 'slug')


def _leak_hits(text, mp):
    """Every leak in text as (label, token, start, end)."""
    hits = [(label, m.group(0)) + m.span() for pat, label in STRUCT for m in re.finditer(pat, text)]
    for n in mp:
        m = re.search(re.escape(n), text, re.I)
        if m:
            hits.append(('full name', n) + m.span())
    pats, runs, entries = _token_patterns(text, mp)
    for label, tok, pat, _ in pats:
        hits += [(label, tok) + m.span() for m in _outside_slots(pat, text, entries=entries)]
    spans = _protected(text, entries)
    hits += [('slug', m.group(0)) + m.span() for m in _SLUG.finditer(text)
             if not _inside(m, spans) and _is_slug(m.group(0).lower(), runs, entries)]
    return hits


def _collapse(hits):
    """leaks()' shape, one entry per token for the single-token passes and one per match otherwise."""
    out, seen = [], set()
    for label, tok, _, _ in hits:
        if label in NAME_KINDS[:3]:
            if (label, tok) in seen:
                continue
            seen.add((label, tok))
        out.append((label, tok))
    return out


def leaks(text, mp):
    return _collapse(_leak_hits(text, mp))


_SLOTS = ('{STAGE_LOG}', '{SCRIPT}', '{RUNLOG}', '{QLOG}', '{CODE}')


def built_prompt(case):
    """The prompt run-shadow.sh builds for this case, byte for byte, the two labels meta.json puts into
    it, and the spans the template's own fixed text holds in it, or None when it cannot be rebuilt. Kept
    in step with run-shadow.sh's own builder. A value that itself holds a slot marker is refused (None):
    run-shadow.sh fills the slots one after another, so "An{QLOG}" in the run log and "as" in the stage
    log would build a name no single file holds (adversary, 2026-10-18). With no marker in any value,
    filling every slot in one pass, as here, builds the same bytes. So does anything this cannot read
    (a missing or unreadable file, a meta.json that does not parse or holds a label that is not text),
    and the prompt then gets the full check instead of a crash."""
    tmpl = pathlib.Path(__file__).parent / 'prompt-template.md'
    try:
        meta = json.loads((case / 'meta.json').read_text()) if (case / 'meta.json').exists() else {'stage': 'Q', 'script': 'Q-follow-up.sh', 'log': 'Q-follow-up.log'}
        labels = (meta.get('log') or 'the stage log', meta.get('script') or 'the stage script')
        values = {'{STAGE_LOG}': labels[0], '{SCRIPT}': labels[1]}
        for k, f in (('RUNLOG', 'input-runlog.txt'), ('QLOG', 'input-qlog.txt'), ('CODE', 'input-code.txt')):
            values['{' + k + '}'] = (case / f).read_text()
        template = tmpl.read_text()
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    if not all(isinstance(v, str) for v in values.values()) or any(s in v for v in values.values() for s in _SLOTS):
        return None
    out, fixed, pos = [], [], 0
    for piece in re.split('(' + '|'.join(re.escape(s) for s in _SLOTS) + ')', template):
        if piece in values:
            piece = values[piece]
        else:
            fixed.append((pos, pos + len(piece)))
        out.append(piece)
        pos += len(piece)
    return ''.join(out), labels, fixed


def prompt_leaks(text, case, mp):
    """leaks() for a built prompt (2026-10-17). When the text is exactly the prompt this case builds, a
    single-token hit lying wholly inside the template's own fixed text is set aside, since those bytes
    are the same in every case's prompt and none of them comes from case data. That keeps a doctrine word
    that matches a roster token from blocking the case, which is the job the old vocabulary filter did by
    hiding names everywhere. Every hit that touches a filled slot is kept, so a name built across a slot
    edge is caught, and whole names and structural patterns are kept everywhere, template included. The
    labels are also scanned on their own. Any other text, or a prompt that does not rebuild byte for
    byte, gets the full check."""
    built = built_prompt(case)
    if built is None or text.rstrip('\n') != built[0].rstrip('\n'):
        return leaks(text, mp)
    fixed = built[2]
    kept = [h for h in _leak_hits(text, mp) if h[0] not in NAME_KINDS or not any(a <= h[2] and h[3] <= b for a, b in fixed)]
    return _collapse(kept) + leaks('\n'.join(built[1]), mp)


def cmd_check(case, extra, mp=None, structural_only=False):
    """mp, when given, is the roster to check against (harvest passes the one it just built, for a case
    still in its staging folder). Otherwise the case's own map from the store. A missing store, or
    a store with no map for this case, refuses the check: with the maps kept apart from the cases, a
    wrong HOME or SHADOW_MAP_DIR or a renamed case folder would otherwise turn the check into a
    structural one without a word (adversary, 2026-10-18). A case with no roster has an empty map
    recorded. structural_only asks for the structural patterns alone, which is all a CI runner with no
    store can check."""
    if structural_only:
        mp = {}
    elif mp is None:
        try:
            if not map_dir().is_dir():
                print(f"REFUSED  the map store {map_dir()} does not exist, so no roster can be checked; "
                      f"set SHADOW_MAP_DIR, or pass --structural-only")
                return 1
            mp = load_map(case)
        except ValueError as e:
            print(f"REFUSED  {e}")
            return 1
        if mp is None:
            print(f"REFUSED  the map store holds no map for {case.name}, and a case is checked against its own roster; "
                  f"harvest it again, or run `compare.py migrate-maps` if it never had one")
            return 1
    own = sorted(case.glob('input-*.txt')) + [case / 'answer-key.md']
    files = own + [pathlib.Path(x) for x in extra]
    bad = 0
    for f in files:
        if not f.exists():
            continue
        hits = leaks(f.read_text(), mp) if f in own else prompt_leaks(f.read_text(), case, mp)
        if hits:
            bad += 1
            print(f"LEAK  {f}")
            for label, tok in sorted(set(hits))[:12]:
                print(f"      {label}: {tok}")
    print(f"check: {len(files)} file(s), roster={'present' if mp else 'absent (structural checks only)'}, leaks in {bad}")
    return 1 if bad else 0


def cmd_compare(case, results):
    key = (case / 'answer-key.md').read_text()
    kclass = re.search(r'Class:\s*(MECHANICAL|JUDGMENT)', key).group(1)
    print(f"answer key: {kclass}\n")
    rc = 0
    for f in results:
        t = pathlib.Path(f).read_text()
        m = re.search(r'SHADOW_RESULT:[\s*]*(MECHANICAL|JUDGMENT)[\s*]*\|\s*(.*)', t)
        cls, summ = (m.group(1), m.group(2).strip()) if m else ('none', '(no verdict line)')
        ok = cls == kclass
        rc = rc if ok else 1
        print(f"{'MATCH' if ok else 'MISS '}  {pathlib.Path(f).name}\n       {cls} | {summ[:220]}\n")
    return rc


def cmd_redact(mapfile, files):
    if _in_repo(mapfile):
        print(f"REFUSED  {mapfile} is a roster map inside the repo; maps belong in the map store")
        return 1
    mp = json.load(open(mapfile))
    for f in files:
        p = pathlib.Path(f)
        p.write_text(redact_text(p.read_text(), mp))
        print(f"redacted {p}")
    return 0


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cmd_scoreboard(args):
    import math
    opts = {'--model': 'glm-5.3', '--engine': 'zai', '--p0': '0.80', '--p1': '0.92', '--alpha': '0.05', '--beta': '0.05', '--split': 'holdout', '--family': 'all'}
    for i, a in enumerate(args):
        if a in opts and i + 1 < len(args):
            opts[a] = args[i + 1]
    model, engine = opts['--model'], opts['--engine']
    p0, p1, alpha, beta = float(opts['--p0']), float(opts['--p1']), float(opts['--alpha']), float(opts['--beta'])
    want_split = opts['--split']
    root = pathlib.Path(__file__).parent
    rows = []
    for case in sorted((root / 'cases').iterdir()):
        if not (case / 'answer-key.md').exists():
            continue
        # The GATE reads holdout only: a set used to tune the instrument is spent (research
        # 2026-08-29). --split dev shows the tuning set, --split all shows everything.
        meta_p = case / 'meta.json'
        split = json.loads(meta_p.read_text()).get('split', 'dev') if meta_p.exists() else 'dev'
        if want_split != 'all' and split != want_split:
            continue
        stage = json.loads(meta_p.read_text()).get('stage', '?') if meta_p.exists() else '?'
        fam = 'render' if stage in ('D', 'E', 'F') else 'ops'
        if opts['--family'] != 'all' and fam != opts['--family']:
            continue
        kclass = re.search(r'Class:\s*(MECHANICAL|JUDGMENT)', (case / 'answer-key.md').read_text())
        if not kclass:
            continue
        tag = model.replace(':', '-').replace('/', '-')
        cands = sorted((root / 'results').glob(f'shadow-{case.name}-{tag}-{engine}-*.md'))
        if case.name == 'q-followup-20260828':
            cands = cands or sorted((root / 'results').glob(f'shadow-{tag}-{engine}-*.md'))
        cands = [c for c in cands if not c.name.endswith('.failed.md') and c.stat().st_size > 0]   # an empty file is a run still in flight
        if not cands:
            rows.append((case.name, kclass.group(1), None, 'pending'))
            continue
        res = cands[-1]
        m = re.search(r'SHADOW_RESULT:[\s*]*(MECHANICAL|JUDGMENT)', res.read_text())
        got = m.group(1) if m else 'none'
        rows.append((case.name, kclass.group(1), got, 'MATCH' if got == kclass.group(1) else 'MISS'))
    scored = [r for r in rows if r[3] in ('MATCH', 'MISS')]
    k = sum(1 for r in scored if r[3] == 'MATCH'); n = len(scored)
    if n == 0:
        for name, key, got, verdict in rows:
            print(f"{verdict:8s} {name:26s} key={key:10s} got={got or '-'}")
        print(f"\n[{want_split}] nothing scored yet ({len(rows)} case(s) pending); gate cannot read.")
        return 1
    lo, hi = wilson(k, n)
    # Wald SPRT on Bernoulli agreement (research 2026-08-29: scan + refute concur on the form)
    la = math.log(beta / (1 - alpha)); lb = math.log((1 - beta) / alpha)
    s = k * math.log(p1 / p0) + (n - k) * math.log((1 - p1) / (1 - p0))
    decision = 'PROMOTE (H1)' if s >= lb else 'REJECT (H0)' if s <= la else 'CONTINUE'
    for name, key, got, verdict in rows:
        print(f"{verdict:8s} {name:26s} key={key:10s} got={got or '-'}")
    print(f"\n[{want_split}] agreement {k}/{n} = {k / n:.0%}  wilson95=[{lo:.0%}, {hi:.0%}]  pending={sum(1 for r in rows if r[3] == 'pending')}")
    print(f"SPRT p0={p0} p1={p1} alpha={alpha} beta={beta}: S={s:+.2f} bounds=[{la:+.2f}, {lb:+.2f}] -> {decision}")
    print(f"(each agreement adds {math.log(p1 / p0):+.3f}, each miss adds {math.log((1 - p1) / (1 - p0)):+.3f}; from zero, ~{math.ceil(lb / math.log(p1 / p0))} straight agreements promote)")
    return 0 if decision.startswith('PROMOTE') else 1


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] not in ('compare', 'check', 'redact', 'scoreboard', 'migrate-maps'):
        print(__doc__); sys.exit(64)
    if a[0] == 'migrate-maps':
        sys.exit(cmd_migrate_maps(a[1] if len(a) > 1 else None))
    if a[0] == 'scoreboard':
        sys.exit(cmd_scoreboard(a[1:]))
    if a[0] == 'compare':
        sys.exit(cmd_compare(pathlib.Path(a[1]), a[2:]))
    if a[0] == 'check':
        so = a[1:2] == ['--structural-only']
        rest = a[2:] if so else a[1:]
        sys.exit(cmd_check(pathlib.Path(rest[0]), rest[1:], structural_only=so))
    sys.exit(cmd_redact(a[1], a[2:]))
