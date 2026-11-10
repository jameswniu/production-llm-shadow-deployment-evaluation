# Run it on your own workflow

This harness replays your agent's past decisions against a second model, the challenger, and scores whether it agrees with your agent often enough to be trusted with the job. It needs three things from you, one seam, one ledger, and patience for the gate.

## 1. Find the seam

The seam is the one place where your agent calls its model. In the fleet this repo studies, the medic (the trusted Claude agent that diagnoses failed scheduled jobs) runs its whole diagnosis through a single model call behind an environment variable. The challenger, the candidate model being tested against the medic, plugs in there and nowhere else. If your agent calls its model in several places, pick the one whose output a person can grade as right or wrong, and leave the rest alone for now.

## 2. Point the harvester at your ledger

`harvest.py` turns past decisions into frozen incidents. It reads one JSON object per line and uses four fields.

| Field | What it holds | Example |
|---|---|---|
| `at` | When the agent decided, as an ISO timestamp | `2026-08-22T18:11:05-07:00` |
| `stage` | Which job or workflow the decision belongs to | `F` |
| `action` | What the agent did, one of `rerun`, `closed` or `annotated` | `rerun` |
| `note` | The agent's own words, including the class it assigned | `Class: MECHANICAL ...` |

The class comes from the note, not the action, because a closed ticket can still be a judgment call. `rerun` and `closed` default to MECHANICAL and `annotated` to JUDGMENT only when the note names no class.

```bash
export SHADOW_LEDGER=/path/to/your/ledger.jsonl
export SHADOW_FLEET=/path/to/the/folder/with/your/job/logs   # optional, defaults to ~/claude-os
cd shadow-medic
python3 harvest.py --dry-run     # shows which incidents it would freeze and why it skips the rest
python3 harvest.py --limit 20    # writes cases/<id>/ folders
```

Each incident folder holds the agent's note as the answer key, the log window from before the decision, and a `meta.json` like this one.

```json
{
  "stage": "F",
  "script": "F-render.sh",
  "log": "F-render.log",
  "split": "holdout",
  "runner_evidence": false,
  "split_basis": "minted after the tune (2026-08-29 PT)"
}
```

`split` is the field the gate reads. Incidents you use while tuning the prompt are `dev`, everything that arrives after the tune is `holdout`, and only holdout rows ever reach the scoreboard. `dev-set.txt` is the append-only list of dev incidents, so the split survives a deleted cases folder.

## 3. Give the challenger the same rulebook

`prompt-template.md` carries the incumbent's own classification rules word for word. Paraphrasing cost one wrong verdict here, so transplant yours verbatim. The template is filled per incident at prompt-build time with the fields from `meta.json`, never with a hard-coded job name.

## 4. Run the shadow and score it

```bash
bash run-shadow.sh api llama3.1:8b cases/<id>              # free local control through Ollama
GLM_API_KEY=your-key bash run-shadow.sh zai glm-5.3 cases/<id>
python3 compare.py compare cases/<id> results/shadow-<id>-*.md
python3 compare.py scoreboard --family ops
```

`run-shadow.sh` scans the exact prompt that is about to leave the machine and refuses with exit 4 if the leak check finds a name, an email or a link. Change the family rule in `compare.py` (`stage in ('D', 'E', 'F')` is render here) to whatever grouping your jobs need, and gate each family on its own.

## 5. Read the gate, then climb one rung

The scoreboard prints CONTINUE until the running score crosses +2.94 (promote) or -2.94 (reject). Each agreement adds about 0.14 and each miss subtracts about 0.92, so 22 straight agreements promote from zero and one miss costs about six and a half agreements. When a family promotes, move it one rung up the ladder in [boundary.md](boundary.md), never two.

## What stays yours

Names are redacted per incident against a roster kept outside the repo, and the redaction map never ships. Before anything leaves the machine, run `python3 compare.py check cases/<id>` and read the hits. Treat the output of this harness as evidence for a decision you still make yourself.
