#!/usr/bin/env python3
"""referee.py <case-dir> <shadow-result.md> [--engine zai] [--model glm-5.3]

Adjudicates ONE incumbent-vs-shadow disagreement. The incumbent (the production medic, the Claude agent
that diagnoses failed scheduled jobs) is the oracle only by convention, and the shadow is the challenger
model tested against it. On a disagreement somebody has to be wrong, and the point of this check is that
it cuts both ways: a referee ruling for the shadow is a free bug report on the incumbent.

Discipline, from the 2026-08-29 research pass (noisy-judge literature) and the house rule that every
ruling gets a second, refuting review:
  - The two positions are presented as A and B in RANDOMIZED order, unlabeled, so the judge cannot
    favour the incumbent by position or by knowing which is the incumbent.
  - The judge rules on the EVIDENCE ONLY, and must quote the line it relies on.
  - Every ruling is then handed to a default-REFUTE adversary (a second call, same inputs, told the
    ruling is probably wrong). Concurrence is required; a split is reported as UNRESOLVED for James,
    never silently collapsed.
Output: JSON on stdout and a row appended to results/referee-log.jsonl.
"""
import json, sys, os, random, re, pathlib, subprocess, datetime, urllib.request

D = pathlib.Path(__file__).parent


def zai(prompt, model='glm-5.3'):
    key = os.environ.get('GLM_API_KEY') or subprocess.run(
        ['security', 'find-generic-password', '-a', os.environ.get('SHADOW_KEYCHAIN_ACCOUNT', os.environ.get('USER', '')), '-s', 'zai-coding', '-w'],
        capture_output=True, text=True).stdout.strip()
    if not key:
        raise SystemExit('no GLM_API_KEY and no keychain entry zai-coding')
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False, 'temperature': 0.1}
    r = urllib.request.Request('https://api.z.ai/api/coding/paas/v4/chat/completions',
                               data=json.dumps(body).encode(),
                               headers={'content-type': 'application/json', 'authorization': 'Bearer ' + key})
    resp = json.load(urllib.request.urlopen(r, timeout=1200))
    return resp['choices'][0]['message'].get('content', '')


def evidence(case):
    parts = []
    for f, label in (('input-runlog.txt', 'run.log window'), ('input-qlog.txt', 'stage log window'), ('input-code.txt', 'code excerpt')):
        p = case / f
        if p.exists():
            parts.append(f'=== {label} ===\n{p.read_text()}')
    return '\n\n'.join(parts)


def positions(case, result_path):
    key = (case / 'answer-key.md').read_text()
    inc_class = re.search(r'Class:\s*(MECHANICAL|JUDGMENT)', key).group(1)
    inc_note = re.search(r'- \d\d:\d\d:\d\d \w+ \| (.*)', key, re.S)
    inc = f'{inc_class}: ' + (inc_note.group(1)[:1200] if inc_note else '')
    res = pathlib.Path(result_path).read_text()
    m = re.search(r'SHADOW_RESULT:[\s*]*(MECHANICAL|JUDGMENT)[\s*]*\|\s*(.*)', res)
    cha = f'{m.group(1)}: {m.group(2)[:1200]}' if m else 'no verdict'
    return inc, cha, inc_class, (m.group(1) if m else None)


JUDGE = """You are adjudicating a disagreement about ONE failed automation stage. Two analysts read the SAME evidence and reached different conclusions. Decide which is better supported BY THE EVIDENCE BELOW, or that they are equivalent.

The only classes are:
- MECHANICAL: the condition is verifiably gone (stale), or is a cleared blocker (rate limit, session limit, killed mid-run, an expired cooldown); remedy is a re-run.
- JUDGMENT: it needs a human decision (a code edit, a config or roster change, a checkpoint hold, spend); remedy is an annotation and the alert stays open.

Rules: rule ONLY on the evidence pasted below; quote the exact line you rely on. If the evidence cannot settle it, say EQUIVALENT. Do not assume either analyst has information you cannot see.

{EV}

=== ANALYST A ===
{A}

=== ANALYST B ===
{B}

Answer in three short lines, nothing else:
QUOTE: <the single evidence line that decides it, verbatim>
WHY: <one sentence>
RULING: <A|B|EQUIVALENT>"""

ADVERSARY = """A judge ruled on the disagreement below. Your job is to REFUTE that ruling: assume it is wrong and look for the reason. Only if you genuinely cannot find one may you concur.

{EV}

=== ANALYST A ===
{A}

=== ANALYST B ===
{B}

=== THE RULING YOU MUST ATTACK ===
{RULING}

Answer in two short lines, nothing else:
WHY: <the strongest case against the ruling, or why it survives>
VERDICT: <REFUTE|CONCUR>"""


def main():
    case = pathlib.Path(sys.argv[1]); result = sys.argv[2]
    model = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else 'glm-5.3'
    # --engine is advertised, so it must be honoured or refused: silently ignoring it would send
    # case evidence to a service the operator did not choose (adversary finding 2026-08-29).
    engine = sys.argv[sys.argv.index('--engine') + 1] if '--engine' in sys.argv else 'zai'
    if engine != 'zai':
        raise SystemExit(f"referee supports --engine zai only (got {engine!r}); refusing to send evidence")
    inc, cha, inc_class, cha_class = positions(case, result)
    if inc_class == cha_class:
        print(json.dumps({'case': case.name, 'status': 'no-disagreement'})); return 0
    ev = evidence(case)
    flip = random.random() < 0.5                      # position randomization: A is not always the incumbent
    A, B = (cha, inc) if flip else (inc, cha)
    who = {'A': 'challenger' if flip else 'incumbent', 'B': 'incumbent' if flip else 'challenger'}
    jt = zai(JUDGE.format(EV=ev, A=A, B=B), model)
    rul = re.search(r'RULING:\s*(A|B|EQUIVALENT)', jt)
    ruling = rul.group(1) if rul else '?'
    at = zai(ADVERSARY.format(EV=ev, A=A, B=B, RULING=jt), model)
    adv = re.search(r'VERDICT:\s*(REFUTE|CONCUR)', at)
    adv_v = adv.group(1) if adv else '?'
    winner = 'EQUIVALENT' if ruling == 'EQUIVALENT' else who.get(ruling, '?')
    status = 'UNRESOLVED (adversary refuted)' if adv_v != 'CONCUR' else f'{winner} favoured'
    row = {'at': datetime.datetime.now().isoformat(timespec='seconds'), 'case': case.name,
           'incumbent_class': inc_class, 'challenger_class': cha_class,
           'a_was': who['A'], 'ruling': ruling, 'winner': winner, 'adversary': adv_v, 'status': status,
           'judge_quote': (re.search(r'QUOTE:\s*(.*)', jt).group(1)[:300] if re.search(r'QUOTE:\s*(.*)', jt) else ''),
           'judge_why': (re.search(r'WHY:\s*(.*)', jt).group(1)[:300] if re.search(r'WHY:\s*(.*)', jt) else ''),
           'adversary_why': (re.search(r'WHY:\s*(.*)', at).group(1)[:300] if re.search(r'WHY:\s*(.*)', at) else '')}
    (D / 'results' / 'referee-log.jsonl').open('a').write(json.dumps(row) + '\n')
    print(json.dumps(row, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
