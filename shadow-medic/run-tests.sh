#!/bin/bash
# Runs every test script in this folder and fails if any of them fails. Standard library only, with no
# keys and no network, so a fresh clone and python3 are enough.
cd "$(dirname "$0")" || exit 2
rc=0
for t in test_*.py; do
    python3 "$t" || { echo "FAILED  $t"; rc=1; }
done
exit $rc
