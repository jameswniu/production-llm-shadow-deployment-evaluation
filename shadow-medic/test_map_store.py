#!/usr/bin/env python3
"""compare.py's map store.

shadow-medic, this folder, is a harness that replays the medic's diagnoses against a challenger model,
where the medic is the automated worker that diagnoses red alerts from scheduled jobs. harvest.py turns
each past alert into a case, a folder of frozen logs plus the medic's note, and compare.py redacts and
checks those files. A case's roster map lists the real names harvest found in it, each mapped to a
placeholder such as [person1], which is what redaction replaces them with.

A roster map is the one file in a case that holds real names, so maps live
outside the repo, where no tool run inside the repo, an adversarial reviewer included, can read one.
These checks pin that harvest and compare write and read maps only there, that nothing writes a map
inside the repo, and that a map left in a case folder is refused rather than skipped.

    python3 shadow-medic/test_map_store.py      exit 0 = all pass
"""
import contextlib
import io
import json
import os
import pathlib
import shutil
import stat
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = pathlib.Path(tempfile.mkdtemp(prefix="shadow-map-test-"))
os.environ["SHADOW_MAP_DIR"] = str(tmp / "store")
import compare  # noqa: E402

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print("  ok    " + name)
    else:
        failed += 1
        print("  FAIL  %s  <- %s" % (name, detail))


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = fn(*a, **k)
    return rc, out.getvalue()


MP = {"Tavio Quenneville": "[person1]"}
try:
    # ---- where the store is ----
    check("SHADOW_MAP_DIR names the store", compare.map_dir() == tmp / "store", compare.map_dir())
    saved_env = os.environ.pop("SHADOW_MAP_DIR")
    check("by default the store is ~/.shadow-os/redaction-maps, outside the repo",
          compare.map_dir() == pathlib.Path.home() / ".shadow-os" / "redaction-maps" and not compare._in_repo(compare.map_dir()))
    os.environ["SHADOW_MAP_DIR"] = saved_env

    # ---- a round trip, owner-only ----
    case = tmp / "cases" / "Z-20260101T0000"
    case.mkdir(parents=True)
    p = compare.save_map(case.name, MP)
    check("a saved map is read back for its case", compare.load_map(case) == MP, compare.load_map(case))
    check("the map is the case name plus .json in the store", p == tmp / "store" / "Z-20260101T0000.json", p)
    check("the map file is owner-only", stat.S_IMODE(p.stat().st_mode) == 0o600, oct(stat.S_IMODE(p.stat().st_mode)))
    check("the store is owner-only", stat.S_IMODE(p.parent.stat().st_mode) == 0o700, oct(stat.S_IMODE(p.parent.stat().st_mode)))
    nomap = tmp / "cases" / "Y-20260101T0000"
    nomap.mkdir()
    (nomap / "input-qlog.txt").write_text("nothing here")
    check("a case with no stored map reads as None, not as an empty roster", compare.load_map(nomap) is None)
    rc, out = quiet(compare.cmd_check, nomap, [])
    check("and its check is refused, so a renamed folder or a lost map cannot pass on structure", rc == 1 and "REFUSED" in out, out)

    # ---- nothing writes a map inside the repo ----
    inside = HERE / "map-store-test-must-not-exist"
    os.environ["SHADOW_MAP_DIR"] = str(inside)
    try:
        compare.save_map("Z-20260101T0000", MP)
        refused = False
    except ValueError:
        refused = True
    check("a store inside the repo is refused", refused and not inside.exists(), inside.exists())
    link = tmp / "link-into-repo"
    link.symlink_to(HERE)
    os.environ["SHADOW_MAP_DIR"] = str(link)
    try:
        compare.save_map("Z-20260101T0000", MP)
        refused = False
    except ValueError:
        refused = True
    check("a store that is a link into the repo is refused", refused and not (HERE / "Z-20260101T0000.json").exists())
    os.environ["SHADOW_MAP_DIR"] = str(HERE)
    try:
        compare.load_map(case)
        refused = False
    except compare.MapInRepo:
        refused = True
    check("reading through a store inside the repo is refused too", refused)
    rc, out = quiet(compare.cmd_check, case, [])
    check("and the check fails closed on it", rc == 1 and "REFUSED" in out, out)
    os.environ["SHADOW_MAP_DIR"] = "relative/store"
    try:
        compare.map_dir()
        refused = False
    except ValueError:
        refused = True
    check("a relative SHADOW_MAP_DIR is refused, since it would move with the working directory", refused)
    os.environ["SHADOW_MAP_DIR"] = saved_env
    planted = tmp / "store" / "W-20260101T0000.json"
    planted.symlink_to(HERE / "prompt-template.md")
    try:
        compare.load_map(tmp / "cases" / "W-20260101T0000")
        refused = False
    except compare.MapInRepo:
        refused = True
    check("a map file that is a link into the repo is refused for reading", refused)
    planted.unlink()
    target = HERE / "planted-map-must-not-exist.json"
    for i in range(3):
        (tmp / "store" / f".Z-20260101T0000.json.planted{i}.tmp").symlink_to(target)
    (tmp / "store" / ".Z-20260101T0000.json.tmp").symlink_to(target)
    loose = compare.map_path("V-20260101T0000")
    loose.write_text("{}")
    loose.chmod(0o644)
    compare.save_map("Z-20260101T0000", MP)
    compare.save_map("V-20260101T0000", MP)
    check("a temp-file link planted in the store cannot redirect a write into the repo",
          not target.exists() and compare.load_map(case) == MP)
    check("a map that was readable by others is replaced owner-only", stat.S_IMODE(loose.stat().st_mode) == 0o600,
          oct(stat.S_IMODE(loose.stat().st_mode)))
    for bad in ("../escape", "a/b", "", ".hidden"):
        try:
            compare.map_path(bad)
            refused = False
        except ValueError:
            refused = True
        check(f"a name that is not a case folder name is refused ({bad!r})", refused)

    # ---- a map left in a case folder is refused, never skipped ----
    legacy_case = tmp / "cases" / "X-20260101T0000"
    legacy_case.mkdir()
    (legacy_case / "input-qlog.txt").write_text("Tavio wrote")
    (legacy_case / compare.LEGACY_MAP).write_text(json.dumps(MP))
    try:
        compare.load_map(legacy_case)
        raised = False
    except compare.MapInRepo:
        raised = True
    check("load_map refuses a map inside a case folder", raised)
    rc, out = quiet(compare.cmd_check, legacy_case, [])
    check("and the check fails closed on it, naming nobody", rc == 1 and "Tavio" not in out and "Quenneville" not in out, out)

    # ---- the check against the roster harvest passes for a case still in its staging folder ----
    stage = tmp / "shadow-harvest-Z-20260101T0000-abc"
    stage.mkdir()
    (stage / "input-qlog.txt").write_text("Tavio wrote")
    (stage / "answer-key.md").write_text("Class: MECHANICAL\n")
    check("cmd_check with the roster given catches a name in a staging folder", quiet(compare.cmd_check, stage, [], mp=MP)[0] == 1)

    # ---- a missing store refuses the check, unless only structure is asked for ----
    os.environ["SHADOW_MAP_DIR"] = str(tmp / "no-such-store")
    rc, out = quiet(compare.cmd_check, case, [])
    check("a missing map store refuses the check instead of checking structure alone", rc == 1 and "REFUSED" in out, out)
    (case / "input-qlog.txt").write_text("mail someone@example.com")
    check("--structural-only still runs the structural patterns", quiet(compare.cmd_check, case, [], structural_only=True)[0] == 1)
    (case / "input-qlog.txt").write_text("nothing here")
    check("and passes a clean case", quiet(compare.cmd_check, case, [], structural_only=True)[0] == 0)
    os.environ["SHADOW_MAP_DIR"] = saved_env

    # ---- harvest promotes a case and its map together ----
    import harvest  # noqa: E402
    hc = tmp / "promote" / "cases" / "P-20260101T0000"
    hc.mkdir(parents=True)
    (hc / "input-qlog.txt").write_text("old case")
    compare.save_map(hc.name, {"Old Entry": "[person1]"})
    st = tmp / "promote" / "stage"
    st.mkdir()
    (st / "input-qlog.txt").write_text("new case")
    real_move = harvest.shutil.move

    def boom(*a, **k):
        raise OSError("disk full")
    harvest.shutil.move = boom
    try:
        harvest.promote(st, hc, hc.name, {"New Entry": "[person1]"})
        failed_move = False
    except OSError:
        failed_move = True
    finally:
        harvest.shutil.move = real_move
    check("a failed promotion puts the store back to the map it held before",
          failed_move and json.loads(compare.map_path(hc.name).read_text()) == {"Old Entry": "[person1]"})
    check("and puts the old case folder back as it was",
          (hc / "input-qlog.txt").exists() and (hc / "input-qlog.txt").read_text() == "old case"
          and not hc.with_name("." + hc.name + ".replaced").exists())
    st2 = tmp / "promote" / "stage2"
    st2.mkdir()
    (st2 / "input-qlog.txt").write_text("new case")
    harvest.shutil.move = boom
    try:
        harvest.promote(st2, tmp / "promote" / "cases" / "Q-20260101T0000", "Q-20260101T0000", {"New Entry": "[person1]"})
    except OSError:
        pass
    finally:
        harvest.shutil.move = real_move
    check("and removes a new map that had no earlier one", not compare.map_path("Q-20260101T0000").exists())
    harvest.promote(st2, tmp / "promote" / "cases" / "Q-20260101T0000", "Q-20260101T0000", {"New Entry": "[person1]"})
    st3 = tmp / "promote" / "stage3"
    st3.mkdir()
    (st3 / "input-qlog.txt").write_text("replacement case")
    harvest.promote(st3, hc, hc.name, {"New Entry": "[person1]"})
    check("a promotion over an existing case replaces it and leaves no backup behind",
          (hc / "input-qlog.txt").read_text() == "replacement case" and not hc.with_name("." + hc.name + ".replaced").exists()
          and compare.load_map(hc) == {"New Entry": "[person1]"})
    check("a promotion that works lands the case and its map together",
          (tmp / "promote" / "cases" / "Q-20260101T0000" / "input-qlog.txt").read_text() == "new case"
          and compare.load_map(tmp / "promote" / "cases" / "Q-20260101T0000") == {"New Entry": "[person1]"})

    # ---- migrate-maps moves maps out, and never overwrites a different one ----
    mig = tmp / "migrate" / "cases"
    for name in ("A-20260101T0000", "B-20260101T0000"):
        (mig / name).mkdir(parents=True)
        (mig / name / compare.LEGACY_MAP).write_text(json.dumps({name + " Quenneville": "[person1]"}))
    compare.save_map("B-20260101T0000", {"Someone Else": "[person1]"})
    rc, out = quiet(compare.cmd_migrate_maps, mig)
    check("migrate-maps moves a map into the store and out of the case folder",
          compare.load_map(mig / "A-20260101T0000") == {"A-20260101T0000 Quenneville": "[person1]"}
          and not (mig / "A-20260101T0000" / compare.LEGACY_MAP).exists())
    check("and leaves both copies of a conflicting map where they are, failing",
          rc == 1 and (mig / "B-20260101T0000" / compare.LEGACY_MAP).exists()
          and json.loads(compare.map_path("B-20260101T0000").read_text()) == {"Someone Else": "[person1]"}, out)
    never = tmp / "migrate2" / "cases" / "C-20260101T0000"
    never.mkdir(parents=True)
    (never / "answer-key.md").write_text("Class: MECHANICAL\n")
    (never / "input-qlog.txt").write_text("nothing here")
    rc, out = quiet(compare.cmd_migrate_maps, never.parent)
    check("migrate-maps records an empty map for a case that never had one",
          rc == 0 and compare.load_map(never) == {} and "EMPTY" in out, out)
    check("which is then checked on structure, as before", quiet(compare.cmd_check, never, [])[0] == 0)

    # ---- compare.py redact will not read a map inside the repo ----
    rc, out = quiet(compare.cmd_redact, str(HERE / "prompt-template.md"), [])
    check("compare.py redact refuses a map path inside the repo", rc == 1 and "REFUSED" in out, out)

    # ---- harvest writes its map to the store only ----
    src = (HERE / "harvest.py").read_text()
    check("harvest.py never names the in-folder map file", compare.LEGACY_MAP not in src)
    check("harvest.py saves the roster through the store", "cmp_mod.save_map(slug, roster)" in src and "promote(stage_dir, case, slug, roster)" in src)
    check("and checks a staged case against the roster it built", "cmd_check(stage_dir, [], mp=roster)" in src)

    # ---- the repo holds no map ----
    left = [str(q.relative_to(compare.REPO)) for q in compare.REPO.rglob(compare.LEGACY_MAP)]
    check("no roster map is left anywhere in the repo tree (run compare.py migrate-maps)", not left, f"{len(left)} found")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
