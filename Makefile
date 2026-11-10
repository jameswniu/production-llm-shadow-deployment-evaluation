.PHONY: figures figures-check verdicts verdicts-check test check

GENS = tools/render_hero.py tools/render_map.py tools/render_panel.py

figures:
	for g in $(GENS); do python3 $$g --write || exit 1; done

figures-check:
	for g in $(GENS); do python3 $$g --check || exit 1; done

verdicts:
	python3 tools/verdicts_table.py --write

verdicts-check:
	python3 tools/verdicts_table.py --check

test:
	cd shadow-medic && bash run-tests.sh

check: figures-check verdicts-check
	python3 shadow-medic/check-readme-scoreboard.py
