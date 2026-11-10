#!/bin/bash
# run-shadow.sh <engine: api|zai|hermes> <model> [case-dir]
# Runs the shadow medic (the challenger model doing the medic's diagnosis job) on one recorded red, one past
# failed run of a scheduled job. Writes results/shadow-<model>-<engine>-<ts>.md on success;
# a failed run (nonzero model exit, or no SHADOW_RESULT line) is renamed *.failed.md and this script exits nonzero,
# so nothing downstream can count it as a usable run.
# api    = the model alone through the local Ollama endpoint (control: no harness, no tools)
# zai    = the model alone through Z.ai coding-plan endpoint (vendor serving; key from GLM_API_KEY or keychain zai-coding)
# hermes = the same prompt through Hermes Agent pointed at the same endpoint, repo-local HERMES_HOME, no tools
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"; ENGINE="${1:-api}"; MODEL="${2:-llama3.1:8b}"; CASE="${3:-$D/cases/F-20260822T1811}"
mkdir -p "$D/results"; TS=$(date +%Y%m%d-%H%M%S); OUT="$D/results/shadow-$(basename "$CASE")-$(echo "$MODEL" | tr ':/' '--')-$ENGINE-$TS.md"
for f in input-runlog.txt input-qlog.txt input-code.txt; do [ -f "$CASE/$f" ] || { echo "no $f in $CASE: that incident is withheld as personal or incomplete, so pick a case folder with all three input-*.txt files" >&2; exit 2; }; done

python3 - "$D/prompt-template.md" "$CASE" > "$D/prompt.built.md" <<'PY'
import sys, pathlib
import json
t = pathlib.Path(sys.argv[1]).read_text(); c = pathlib.Path(sys.argv[2])
meta = json.load(open(c / 'meta.json')) if (c / 'meta.json').exists() else {'stage': '?', 'script': 'unknown-job.sh', 'log': 'unknown-job.log'}
t = t.replace('{STAGE_LOG}', meta.get('log') or 'the stage log').replace('{SCRIPT}', meta.get('script') or 'the stage script')
for k, f in (('RUNLOG', 'input-runlog.txt'), ('QLOG', 'input-qlog.txt'), ('CODE', 'input-code.txt')):
    t = t.replace('{' + k + '}', (c / f).read_text())
assert '{RUNLOG}' not in t and '{QLOG}' not in t and '{CODE}' not in t and '{STAGE_LOG}' not in t
print(t)
PY
# Preflight on the BUILT prompt (adversary finding 2026-08-29): the check must cover the exact bytes that leave the
# machine, which now include meta.json-derived labels and the template itself, not just the case inputs.
if ! python3 "$D/compare.py" check "$CASE" "$D/prompt.built.md"; then
    if [ "$ENGINE" = "zai" ] || [ "$ENGINE" = "hermes" ] || case "$MODEL" in *cloud*) true ;; *) false ;; esac; then
        echo "!! redaction check failed and this run leaves the machine: refusing to send" >&2; exit 4
    fi
    echo "!! redaction check failed (local model, continuing)" >&2
fi
START=$(date +%s); RC=0
case "$ENGINE" in
  api)
    python3 - "$D/prompt.built.md" "$MODEL" > "$OUT" <<'PY' || RC=$?
import sys, json, urllib.request
p = open(sys.argv[1]).read(); m = sys.argv[2]
body = {"model": m, "messages": [{"role": "user", "content": p}], "stream": False, "options": {"temperature": 0.2, "num_ctx": 32768}}
r = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(), headers={"content-type": "application/json"})
resp = json.load(urllib.request.urlopen(r, timeout=1200))
if "error" in resp:
    print("ERROR:", resp["error"]); sys.exit(2)
print(resp["message"].get("content", ""))
print("\n---\nmeta:", json.dumps({k: resp.get(k) for k in ("model", "total_duration", "eval_count", "prompt_eval_count", "done_reason")}))
PY
    ;;
  zai)
    # Z.ai GLM Coding Plan: the vendor serving of the reference FP8 checkpoint, flat fee.
    KEY="${GLM_API_KEY:-$(security find-generic-password -a "${SHADOW_KEYCHAIN_ACCOUNT:-$USER}" -s zai-coding -w 2>/dev/null || true)}"
    [ -n "$KEY" ] || { echo "no GLM_API_KEY env and no keychain entry (service zai-coding)" >&2; exit 5; }
    ZAI_KEY="$KEY" python3 - "$D/prompt.built.md" "$MODEL" > "$OUT" <<'PY' || RC=$?
import sys, json, os, urllib.request
p = open(sys.argv[1]).read(); m = sys.argv[2]
body = {"model": m, "messages": [{"role": "user", "content": p}], "stream": False, "temperature": 0.2}
r = urllib.request.Request("https://api.z.ai/api/coding/paas/v4/chat/completions", data=json.dumps(body).encode(),
                           headers={"content-type": "application/json", "authorization": "Bearer " + os.environ["ZAI_KEY"]})
resp = json.load(urllib.request.urlopen(r, timeout=1200))
if "error" in resp:
    print("ERROR:", resp["error"]); sys.exit(2)
ch = resp["choices"][0]["message"]
print(ch.get("content", ""))
print("\n---\nmeta:", json.dumps(resp.get("usage", {})))
PY
    ;;
  hermes)
    # shellcheck source=../bin/hermes-env.sh
    . "$D/../bin/hermes-env.sh"
    # Frozen-instrument guard: oneshot mode injects MEMORY.md/USER.md when they exist, so a memory
    # file appearing in the repo-local home would silently turn this lane into a moving target
    # mid-certification. Refuse until the gate is closed; ALLOW_HERMES_MEMORY=1 lifts it on deploy.
    if [ "${ALLOW_HERMES_MEMORY:-}" != "1" ] && [ -s "$HERMES_HOME/memories/MEMORY.md" -o -s "$HERMES_HOME/memories/USER.md" ]; then
        echo "!! hermes home carries a non-empty memory file; the certification instrument is frozen." >&2
        echo "!! remove it, or set ALLOW_HERMES_MEMORY=1 after promotion." >&2; exit 6
    fi
    GLM_API_KEY="${GLM_API_KEY:-$(security find-generic-password -a "${SHADOW_KEYCHAIN_ACCOUNT:-$USER}" -s zai-coding -w 2>/dev/null || true)}" hermes chat --oneshot -Q --query-file "$D/prompt.built.md" -m "$MODEL" ${HERMES_PROVIDER:+--provider "$HERMES_PROVIDER"} -t safe > "$OUT" 2> "$OUT.err" || RC=$?
    ;;
  *) echo "engine must be api|zai|hermes" >&2; exit 64 ;;
esac
ELAPSED=$(( $(date +%s) - START ))
if [ "$RC" -ne 0 ]; then mv "$OUT" "${OUT%.md}.failed.md"; echo "FAILED rc=$RC elapsed=${ELAPSED}s -> ${OUT%.md}.failed.md" >&2; exit "$RC"; fi
if ! grep -a -q 'SHADOW_RESULT:' "$OUT"; then mv "$OUT" "${OUT%.md}.failed.md"; echo "FAILED no SHADOW_RESULT line elapsed=${ELAPSED}s -> ${OUT%.md}.failed.md" >&2; exit 3; fi
echo "ok elapsed=${ELAPSED}s out=$OUT"; grep -a 'SHADOW_RESULT:' "$OUT" | tail -1
