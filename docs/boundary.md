# How far the challenger is trusted, and what leaves the machine

The medic is one scheduled job in my fleet. A shell script collects the alerts for failed jobs, and a single Claude call writes each diagnosis and decides what to do. That one model call is the seam, the only place a new model has to fit.

## The trust ladder

Each rung is verified on recorded incidents before the next one starts.

1. **Shadow, no tools.** This repo, today. The challenger gets the same evidence the medic saw, with no messaging token, no keychain and no file or terminal tools, and writes to its own results folder. Its answer is compared with the medic's verdict for the same incident, and nothing it says reaches anyone.
2. **Shadow, read-only tools.** The challenger gets read-only access to the fleet's logs and scripts, so it has to find the evidence itself. It still posts nothing.
3. **Live diagnosis, Claude still acts.** The challenger writes the diagnosis, and the Claude medic or a plain script still decides whether to rerun the job, and does the posting.
4. **The swap, behind a flag.** One environment variable at the seam switches each family that cleared, with the same prompt contract, ledger and limits.

Promotion between rungs needs a run of recorded incidents where the class agrees and no evidence is invented, which means every cited line must exist in the inputs. A wrong class or one fabricated log line resets the count.

## What leaves the machine

Before any cloud-bound run, a preflight scans the exact prompt that would be sent, and a run that fails the leak check refuses and exits. Incident logs committed here had names redacted with a per-incident roster that stays local, and this public copy adds a second scrub of paths, links, emails and ids. Incidents from jobs that act on my personal accounts ship only their verdict fields.

## Rules the first incidents taught

Every early miss but one was the measuring stick, not the model. Each rule below cost one wrong verdict.

- **Evidence windows look only backward.** A window that reached past the incident let the challenger see the job recover and call a still-open fault healed, on evidence the medic never had. On a backward-only window the same incident matched.
- **One fault, one case.** The ledger writes a second row when a watcher reports the same fault, and a case minted from that row carries the wrong job's log. The harvester now skips those rows.
- **Evidence labels come from the incident, never the template.** The first template hard-coded one job's log names, so every job's evidence was labelled as that job's. The challenger flagged the mismatch in its own answer before the harness caught it.
- **The rulebook transfers word for word.** A compressed rule set dropped "a glass void-stability hold is a re-roll, not a judgment call", and incident F-20260826T1827 was called JUDGMENT until the medic's classification section was copied verbatim. Then the challenger applied the rule by name.
- **The class comes from the medic's own words.** A closed or rerun action can follow a judgment call, so the note decides, not the verb.
- **Never grade a file that is still being written.** Runners create their output first, so an empty result is pending, not a miss.
- **Tuning incidents never reach the gate.** The first incidents tuned the prompt and are marked dev, and the gate reads only incidents that arrived after. A tight non-inferiority claim near 90% would need on the order of 400 of them, which is why the corpus grows on its own instead of in one batch.
