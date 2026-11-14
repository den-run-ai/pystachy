"""Tests of the Lean verification report's tallies, rendering and input digests, and of how its
workers compile programs and share results (lean_report.py).

They need no Lean checker: records are made by hand, as check_program makes them, and the
committed report is checked for its form, not rerun."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import lean_report as report

META = {"commit": "0123456789ab", "date": "2026-11-13", "python": "3.13.0", "lean": "Lean 4.35.0", "minutes": 30,
        "completion": {"version": 1, "expected": report.inventory(["a.py"]),
                       "evaluated": report.inventory(["a.py"]), "promoting": report.inventory([]), "failed": 0},
        "inputs": {"checkers": {"digest": "c" * 16, "clean": True},
                   "compiler": {"digest": "a" * 16, "clean": True},
                   "corpus": {"digest": "b" * 16, "clean": True}}}


def row(obligations, proved, functions=1, unproved=()):
    return {"functions": functions, "obligations": obligations, "proved": proved, "unproved": list(unproved)}


def item(function, status="rejected", obligations=2, reason="a transfer is not justified"):
    return {"function": function, "status": status, "obligations": obligations, "reason": reason}


def record(program, **checks):
    """A program's record with every check of a program that does not opt in to promoting ints."""
    full = {key: row(0, 0, 0) for key, *_ in report.CHECKS if key not in ("int", "int_inline", "storage")}
    return {"program": program, "checks": dict(full, **checks), "seconds": 1.0}


class SummaryTests(unittest.TestCase):
    def test_a_module_function_rejected_in_several_programs_is_listed_once(self):
        shared = item("@m.logging$Manager.getLogger.2")
        records = [record("a.py", fields=row(10, 8, 3, [shared])), record("b.py", fields=row(4, 2, 2, [shared])),
                   record("c.py", fields=row(5, 5, 1)), record("d.py")]
        fields = report.summarize(records)["checks"]["fields"]
        self.assertEqual((fields["programs"], fields["functions"], fields["obligations"], fields["proved"]),
                         (3, 6, 19, 15))
        self.assertEqual(fields["rejected"], [{"function": "@m.logging$Manager.getLogger", "programs": ["a.py", "b.py"],
                                               "obligations": 4, "reason": shared["reason"]}])

    def test_a_program_function_is_its_programs_own(self):
        records = [record("a.py", gc=row(3, 1, 1, [item("@main.init")])),
                   record("b.py", gc=row(3, 1, 1, [item("@main.init", reason="another reason")]))]
        rejected = report.summarize(records)["checks"]["gc"]["rejected"]
        self.assertEqual([(r["function"], r["programs"], r["reason"]) for r in rejected],
                         [("@main.init", ["a.py"], "a transfer is not justified"),
                          ("@main.init", ["b.py"], "another reason")])

    def test_unsupported_functions_are_counted_by_their_reason(self):
        records = [record("a.py", union=row(5, 0, 3, [item("@f.g.1", "unsupported", None, "generators are outside"),
                                                      item("@f.g.2", "unsupported", None, "generators are outside"),
                                                      item("@f.h", "error", None, "union read %t3 at L4:2")])),
                   record("b.py", union=row(2, 0, 1, [item("@f.k", "unsupported", None, "generators are outside")]))]
        other = report.summarize(records)["checks"]["union"]["other"]
        self.assertEqual(other, [{"status": "error", "reason": "union read", "programs": 1, "functions": 1},
                                 {"status": "unsupported", "reason": "generators are outside", "programs": 2,
                                  "functions": 2}])

    def test_programs_and_checks_that_failed_are_kept(self):
        partial = record("b.py")
        partial["failed"] = {"guard_checks": "a malformed snapshot"}
        summary = report.summarize([{"program": "a.py", "error": "inspection failed", "seconds": 1.0}, partial])
        self.assertEqual(summary["programs"], 2)
        self.assertEqual(summary["failed"], [{"program": "a.py", "reason": "inspection failed"},
                                             {"program": "b.py", "reason": "guard_checks: a malformed snapshot"}])

    def test_order_does_not_depend_on_completion(self):
        first = [record("a.py", gc=row(3, 1, 2, [item("@m.x$f"), item("@m.x$g", obligations=1)])),
                 record("b.py", gc=row(2, 0, 1, [item("@m.x$g", obligations=1)]))]
        self.assertEqual(report.summarize(first), report.summarize(first[::-1]))
        self.assertEqual([f["function"] for f in report.summarize(first)["checks"]["gc"]["rejected"]],
                         ["@m.x$f", "@m.x$g"])

    def test_names_and_reasons_drop_what_makes_them_one_functions_own(self):
        self.assertEqual(report.base("@f._pystachy_copy$_memo_get.13"), "@f._pystachy_copy$_memo_get")
        self.assertEqual(report.base("@main.init"), "@main.init")
        self.assertEqual(report.kind("union read has no declared source domain: %t33"),
                         "union read has no declared source domain")
        self.assertEqual(report.kind("gives an object to unsupported ['@m.A.__init__']"), "gives an object to unsupported")
        self.assertEqual(report.kind("union payload bits of no known member at L67:4"),
                         "union payload bits of no known member")

    def test_reasons_are_short_text(self):
        found = report.unproved([{"function": "@f", "status": "rejected", "obligations": 1,
                                  "error": [{"node": 3, "known": []}]},
                                 {"function": "@g", "status": "accepted", "obligations": 4},
                                 {"function": "@h", "status": "unsupported", "message": "a  b\n" * 100}],
                                "obligations")
        self.assertEqual([f["function"] for f in found], ["@f", "@h"])
        self.assertEqual(found[0]["reason"], '[{"known": [], "node": 3}]')
        self.assertEqual(len(found[1]["reason"]), report.MESSAGE)
        self.assertTrue(found[1]["reason"].startswith("a b a b"))


class RenderTests(unittest.TestCase):
    def test_every_check_has_a_row_and_the_inputs_are_recorded(self):
        records = [record("a.py", union=row(5, 3, 2, [item("@u", "unsupported", None, "a generator")]),
                          gc=row(4, 2, 1, [item("@m.x$f.2")]), int=row(1, 1), int_inline=row(2, 2), storage=row(3, 3))]
        text = report.render(report.summarize(records), META)
        for _, title, document, _ in report.CHECKS:
            self.assertIn(f"| [{title}]({document}) |", text)
        self.assertIn("| 1 | 2 | 3 of 5 reads | 0 | 1 |", text)
        self.assertIn("- unsupported, 1 function in 1 program: a generator", text)
        self.assertIn("- `@m.x$f` in `a.py`, 2 obligations: a transfer is not justified", text)
        self.assertIn("did not complete:\n\n- none\n", text)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "REPORT.md"
            path.write_text(text)
            self.assertEqual(report.recorded(path), META["inputs"])

    def test_long_lists_are_cut(self):
        items = [item(f"@f{i}") for i in range(report.LISTED + 3)]
        text = report.render(report.summarize([record("a.py", gc=row(100, 0, len(items), items))]), META)
        self.assertEqual(text.count("in `a.py`, 2 obligations"), report.LISTED)
        self.assertIn("- and 3 more rejected functions", text)


class RecordFileTests(unittest.TestCase):
    def test_a_cut_last_line_is_dropped_and_the_last_record_of_a_program_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.jsonl"
            first, again = dict(record("a.py"), seconds=60.0), dict(record("a.py"), seconds=90.0)
            path.write_text("\n".join(json.dumps(line) for line in (
                {"header": {"commit": "x"}}, first, record("b.py"), again)) + '\n{"program": "c.p')
            header, records = report.load(path)
            self.assertEqual(header, {"commit": "x"})
            self.assertEqual(sorted(r["program"] for r in records), ["a.py", "b.py"])
            self.assertEqual(report.meta(header, records)["minutes"], 2)
            path.write_text(json.dumps({"header": {}}) + '\n{"program"\n' + json.dumps(record("a.py")) + "\n")
            with self.assertRaises(ValueError):
                report.load(path)


class ResumeCheckerTests(unittest.TestCase):
    def test_resume_requires_unchanged_readable_checker_executables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checker, access = root / "boundary", root / "access"
            for path in (checker, access):
                path.write_bytes(b"original checker")
            argv = ["--jobs", "1", "--checker", str(checker), "--access-checker", str(access),
                    "--records", str(root / "records.jsonl"), "--output", str(root / "report.md"), "first.py"]
            found = {group: dict(item, clean=True) for group, item in META["inputs"].items()}
            with mock.patch.object(report, "inputs", return_value=found), \
                    mock.patch.object(report.storage_corpus, "select", return_value=[]), \
                    mock.patch.object(report, "check_program", return_value=record("first.py")) as checked, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(report.main(argv), 0)
                self.assertEqual(checked.call_count, 1)
                original = (root / "records.jsonl").read_bytes()
                self.assertEqual(report.main([*argv, "--resume"]), 0)
                self.assertEqual(checked.call_count, 1)  # unchanged proofs are reused
                with mock.patch.object(report.sys, "platform", "other-host"), self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                for path in (checker, access):
                    with self.subTest(changed=path.name):
                        path.write_bytes(b"replacement checker")
                        with self.assertRaises(SystemExit):
                            report.main([*argv, "--resume"])
                        self.assertEqual((root / "records.jsonl").read_bytes(), original)
                        path.write_bytes(b"original checker")
                alternate = root / "alternate"
                alternate.write_bytes(checker.read_bytes())
                changed_path = [str(alternate) if arg == str(checker) else arg for arg in argv]
                with self.assertRaises(SystemExit):
                    report.main([*changed_path, "--resume"])
                access.unlink()
                with self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                self.assertEqual((root / "records.jsonl").read_bytes(), original)
                self.assertEqual(checked.call_count, 1)


class ResumeInputTests(unittest.TestCase):
    def test_dirty_and_legacy_records_cannot_certify_clean_inputs(self):
        # Keep the index unchanged while changing the consumed working files.
        # These are real Git identities and cleanliness checks; only proof work
        # is replaced, so a stale resume is observable as a skipped check_program.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {"compiler": "src/compiler.py", "checkers": "tools/check_lean_probe.py",
                       "corpus": "tests/programs/probe.py"}
            for name in [*sources.values(), "tools/lean_boundary/lean-toolchain"]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("leanprover/lean4:v4.35.0\n" if name.endswith("lean-toolchain") else "# original\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                            "commit", "-qm", "initial inputs"], cwd=root, check=True)
            checker, access = root / "boundary", root / "access"
            for path in (checker, access):
                path.write_bytes(b"checker")
            records, experiment, committed = root / "records.jsonl", root / "experiment.md", root / "REPORT.md"
            argv = ["--jobs", "1", "--checker", str(checker), "--access-checker", str(access),
                    "--records", str(records)]
            with mock.patch.object(report, "ROOT", root), mock.patch.object(report, "REPORT", committed), \
                    mock.patch.object(report.corpus, "corpus", return_value=[sources["corpus"]]), \
                    mock.patch.object(report.storage_corpus, "select", return_value=[]), \
                    mock.patch.object(report, "check_program", return_value=record(sources["corpus"])) as checked, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                clean = report.inputs()
                self.assertTrue(all(item["clean"] for item in clean.values()))
                for group, name in sources.items():
                    source = root / name
                    source.write_text("# dirty first\n")
                    self.assertEqual(report.inputs()[group]["digest"], clean[group]["digest"])
                    self.assertEqual(report.main([*argv, "--output", str(experiment)]), 0)
                    before = records.read_bytes()
                    calls = checked.call_count
                    source.write_text("# dirty second\n")
                    self.assertEqual(report.inputs()[group]["digest"], clean[group]["digest"])
                    with self.subTest(group=group, action="dirty resume"):
                        with self.assertRaises(SystemExit):
                            report.main([*argv, "--output", str(experiment), "--resume"])
                    source.write_text("# original\n")
                    self.assertEqual(report.inputs(), clean)
                    with self.subTest(group=group, action="clean resume"):
                        with self.assertRaises(SystemExit):
                            report.main([*argv, "--resume"])
                    with self.subTest(group=group, action="clean report"):
                        self.assertFalse(committed.exists(), "dirty proofs must not publish the clean report")
                    with self.subTest(group=group, action="status"):
                        self.assertEqual(report.status(experiment), 1)
                    self.assertEqual(records.read_bytes(), before)
                    self.assertEqual(checked.call_count, calls)
                    committed.write_text("existing verified report\n")
                    with self.subTest(group=group, action="render"), self.assertRaises(SystemExit):
                        report.main([*argv, "--render"])
                    with self.subTest(group=group, action="render output"):
                        self.assertEqual(committed.read_text(), "existing verified report\n")
                    committed.unlink(missing_ok=True)
                # Clean, same-input resumes still reuse checked programs.
                self.assertEqual(report.main(argv), 0)
                calls = checked.call_count
                self.assertEqual(report.main([*argv, "--resume"]), 0)
                self.assertEqual(checked.call_count, calls)
                clean_records = records.read_bytes()
                # Rendering is historical output only, even with clean records:
                # the full-run path certifies corpus and execution identities.
                with self.assertRaises(SystemExit):
                    report.main([*argv, "--render"])
                # Legacy headers cannot distinguish this clean run from a dirty
                # experimental run, so they must not be accepted implicitly.
                header, rows = report.load(records)
                for item in header["inputs"].values():
                    item.pop("clean", None)
                records.write_text("\n".join(json.dumps(line) for line in [{"header": header}, *rows]) + "\n")
                legacy = records.read_bytes()
                with self.subTest(action="legacy resume"), self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                self.assertEqual(records.read_bytes(), legacy)
                self.assertEqual(checked.call_count, calls)
                before = committed.read_bytes()
                with self.subTest(action="legacy render"), self.assertRaises(SystemExit):
                    report.main([*argv, "--render"])
                with self.subTest(action="legacy render output"):
                    self.assertEqual(committed.read_bytes(), before)
                experiment.write_text(report.render(report.summarize(rows), report.meta(header, rows)))
                with self.subTest(action="legacy status"):
                    self.assertEqual(report.status(experiment), 1)
                # Historical rendering cannot overwrite the canonical report for
                # different current inputs, whether the change is committed or not.
                records.write_bytes(clean_records)
                before = committed.read_bytes()
                source = root / sources["compiler"]
                source.write_text("# changed compiler\n")
                with self.subTest(action="render dirty checkout"), self.assertRaises(SystemExit):
                    report.main([*argv, "--render"])
                subprocess.run(["git", "add", sources["compiler"]], cwd=root, check=True)
                subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                                "commit", "-qm", "changed compiler"], cwd=root, check=True)
                self.assertTrue(all(item["clean"] for item in report.inputs().values()))
                with self.subTest(action="render changed clean checkout"), self.assertRaises(SystemExit):
                    report.main([*argv, "--render"])
                self.assertEqual(committed.read_bytes(), before)
                # Alternate output keeps the old, visibly stale provenance.
                self.assertEqual(report.main([*argv, "--render", "--output", str(experiment)]), 0)
                self.assertEqual(report.status(experiment), 1)
                source.write_text("# original\n")
                subprocess.run(["git", "add", sources["compiler"]], cwd=root, check=True)
                subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                                "commit", "-qm", "restore compiler"], cwd=root, check=True)
                for group_change in ("missing", "extra"):
                    header, rows = report.load(records)
                    if group_change == "missing":
                        del header["inputs"]["compiler"]
                    else:
                        header["inputs"]["extra"] = {"digest": "d" * 16, "clean": True}
                    records.write_text("\n".join(json.dumps(line) for line in [{"header": header}, *rows]) + "\n")
                    for action in ("--resume", "--render"):
                        with self.subTest(groups=group_change, action=action), self.assertRaises(SystemExit):
                            report.main([*argv, action])
                    self.assertEqual(committed.read_bytes(), before)
                    self.assertEqual(report.main([*argv, "--render", "--output", str(experiment)]), 0)
                    self.assertEqual(report.status(experiment), 1)
                    records.write_bytes(clean_records)
                self.assertEqual(checked.call_count, calls)


class ImportInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.write(".gitignore", "ignored_*.py\nhelper.py\nignored_pkg/\ninspect_compiler/\nbuild/\n__pycache__/\n")
        self.write("tests/probe.py", "from helper import value\nprint(value())\n")
        self.write("tools/lean_boundary/lean-toolchain", "leanprover/lean4:v4.35.0\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.commit()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def commit(self):
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "test inputs"], cwd=self.root, check=True)

    def snapshot(self):
        # Compile the fixture's real source/search paths with the real compiler
        # and library. Sidecars are relative to the fixture, not this checkout.
        compiled = report.compiled

        def with_search_path(path, output, env, timeout):
            env = dict(env, PYSTACHY_PATH=":".join(str(self.root / part)
                       for part in env.get("PYSTACHY_PATH", "").split(":") if part))
            return compiled(path, output, env, timeout)

        with mock.patch.object(report, "compiled", side_effect=with_search_path):
            return report.inspect(str(self.root / "tests/probe.py"), 120)[1]

    def assert_changed_source_cannot_resume(self, change):
        before_snapshot = self.snapshot()
        checker = self.write("checker", "checker")
        records, output = self.root / "records.jsonl", self.root / "report.md"
        argv = ["--jobs", "1", "--checker", str(checker), "--access-checker", str(checker),
                "--records", str(records), "--output", str(output)]
        with mock.patch.object(report.corpus, "corpus", return_value=["tests/probe.py"]), \
                mock.patch.object(report.storage_corpus, "select", return_value=[]), \
                mock.patch.object(report, "check_program", return_value=record("tests/probe.py")) as checked, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with mock.patch.object(report, "ROOT", self.root):
                self.assertEqual(report.main(argv), 0)
                original = records.read_bytes()
                before = report.inputs()
            change()
            self.assertNotEqual(before_snapshot, self.snapshot())
            with mock.patch.object(report, "ROOT", self.root):
                after = report.inputs()
                self.assertEqual({key: item["digest"] for key, item in before.items()},
                                 {key: item["digest"] for key, item in after.items()})
                with self.subTest(action="resume"), self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                with self.subTest(action="status"):
                    self.assertEqual(report.status(output), 1)
                self.assertEqual(records.read_bytes(), original)
                self.assertEqual(checked.call_count, 1)

    def test_source_link_to_non_source_target_cannot_resume(self):
        target = self.write("fixtures/helper.txt", "def value() -> int:\n    return 11\n")
        (self.root / "tests/helper.py").symlink_to("../fixtures/helper.txt")
        subprocess.run(["git", "add", "-f", "tests/helper.py"], cwd=self.root, check=True)
        self.commit()
        self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))

    def test_ignored_intermediate_source_link_cannot_resume(self):
        self.write("fixtures/first.py", "def value() -> int:\n    return 11\n")
        self.write("fixtures/second.py", "def value() -> int:\n    return 29\n")
        (self.root / ".gitignore").write_text((self.root / ".gitignore").read_text() + "bridge\n")
        bridge = self.root / "tests/bridge"
        bridge.symlink_to("../fixtures/first.py")
        (self.root / "tests/helper.py").symlink_to("bridge")
        subprocess.run(["git", "add", "-f", "tests/helper.py"], cwd=self.root, check=True)
        self.commit()

        def retarget():
            bridge.unlink()
            bridge.symlink_to("../fixtures/second.py")

        self.assert_changed_source_cannot_resume(retarget)

    def nested_source(self, *, git_file=False, gitlink=False):
        target = self.write("nested/helper.py", "def value() -> int:\n    return 11\n")
        nested = target.parent
        args = ["--separate-git-dir", str(self.root / ".git/nested-metadata")] if git_file else []
        subprocess.run(["git", "init", "-q", *args, str(nested)], check=True)
        subprocess.run(["git", "add", "."], cwd=nested, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "nested source"], cwd=nested, check=True)
        (self.root / ".gitignore").write_text((self.root / ".gitignore").read_text() + "nested/\n")
        self.write("tests/probe.path", "nested\n")
        if gitlink:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=nested, check=True,
                                  capture_output=True, text=True).stdout.strip()
            subprocess.run(["git", "update-index", "--add", "--cacheinfo", f"160000,{head},nested"],
                           cwd=self.root, check=True)
        self.commit()
        return target

    def test_ignored_nested_repository_cannot_resume(self):
        target = self.nested_source()
        self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))

    def test_nested_repository_git_file_cannot_resume(self):
        target = self.nested_source(git_file=True)
        self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))

    def test_gitlink_source_cannot_resume(self):
        target = self.nested_source(gitlink=True)
        self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))

    def test_git_metadata_import_path_cannot_resume(self):
        target = self.write(".git/fixture/helper.py", "def value() -> int:\n    return 11\n")
        self.write("tests/probe.path", ".git/fixture\n")
        self.commit()
        self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))

    def test_hidden_import_directory_link_cannot_resume(self):
        self.write("fixtures/first/helper.py", "def value() -> int:\n    return 11\n")
        self.write("fixtures/second/helper.py", "def value() -> int:\n    return 29\n")
        subprocess.run(["git", "add", "-f", "fixtures"], cwd=self.root, check=True)
        bridge = self.root / ".git/imports"
        bridge.symlink_to("../fixtures/first", target_is_directory=True)
        self.write("tests/probe.path", ".git/imports\n")
        self.commit()

        def retarget():
            bridge.unlink()
            bridge.symlink_to("../fixtures/second", target_is_directory=True)

        self.assert_changed_source_cannot_resume(retarget)

    def test_status_suppression_cannot_hide_changed_working_source(self):
        target = self.write("tests/helper.py", "def value() -> int:\n    return 11\n")
        subprocess.run(["git", "add", "-f", "tests/helper.py"], cwd=self.root, check=True)
        self.commit()
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                subprocess.run(["git", "update-index", "--" + flag, "tests/helper.py"], cwd=self.root, check=True)
                self.assert_changed_source_cannot_resume(lambda: target.write_text("def value() -> int:\n    return 29\n"))
                target.write_text("def value() -> int:\n    return 11\n")
                subprocess.run(["git", "update-index", "--no-" + flag, "tests/helper.py"], cwd=self.root, check=True)

    def test_indexed_link_chains_and_byte_identical_flagged_inputs_remain_clean(self):
        self.write("fixtures/real/value.py", "def value() -> int:\n    return 11\n")
        (self.root / "fixtures/alias").symlink_to("real", target_is_directory=True)
        (self.root / "tests/bridge").symlink_to("../fixtures/alias/value.py")
        (self.root / "tests/helper.py").symlink_to("bridge")
        subprocess.run(["git", "add", "-f", "tests/helper.py"], cwd=self.root, check=True)
        self.commit()
        with mock.patch.object(report, "ROOT", self.root):
            before = report.inputs()
            self.assertTrue(report.clean_inputs(before))
            for flag in ("assume-unchanged", "skip-worktree"):
                subprocess.run(["git", "update-index", "--" + flag, "fixtures/real/value.py"], cwd=self.root, check=True)
                self.assertEqual(report.inputs(), before)
                subprocess.run(["git", "update-index", "--no-" + flag, "fixtures/real/value.py"], cwd=self.root, check=True)

    def test_ignored_helper_changes_actual_snapshot_and_cannot_resume(self):
        program = self.root / "tests/probe.py"
        helper = self.write("tests/helper.py", "def value() -> int:\n    return 11\n")
        # Use the real compiler and its library, with this real Git fixture's
        # program/import directory. Only the later Lean verdict work is mocked.
        _, first = report.inspect(str(program), 120)
        checker = self.write("checker", "checker")
        records, output = self.root / "records.jsonl", self.root / "report.md"
        argv = ["--jobs", "1", "--checker", str(checker), "--access-checker", str(checker),
                "--records", str(records), "--output", str(output)]
        with mock.patch.object(report.corpus, "corpus", return_value=["tests/probe.py"]), \
                mock.patch.object(report.storage_corpus, "select", return_value=[]), \
                mock.patch.object(report, "check_program", return_value=record("tests/probe.py")) as checked, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with mock.patch.object(report, "ROOT", self.root):
                self.assertEqual(report.main(argv), 0)
                original = records.read_bytes()
                before = report.inputs()
            helper.write_text("def value() -> int:\n    return 29\n")
            _, second = report.inspect(str(program), 120)
            self.assertNotEqual(first, second)
            with mock.patch.object(report, "ROOT", self.root):
                self.assertEqual(report.inputs()["corpus"]["digest"], before["corpus"]["digest"])
                with self.subTest(action="resume"), self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                with self.subTest(action="status"):
                    self.assertEqual(report.status(output), 1)
                helper.unlink()
                with self.subTest(action="cleaned resume"), self.assertRaises(SystemExit):
                    report.main([*argv, "--resume"])
                with self.subTest(action="cleaned status"):
                    self.assertEqual(report.status(output), 1)
                self.assertEqual(records.read_bytes(), original)
                self.assertEqual(checked.call_count, 1)

    def test_ignored_source_packages_and_reference_copies_are_untrusted(self):
        with mock.patch.object(report, "ROOT", self.root):
            clean = report.inputs()
            self.assertTrue(report.clean_inputs(clean))
            # Normal bytecode caches are not source inputs.
            self.write("src/__pycache__/compiler.cpython-313.pyc", "cache")
            self.assertEqual(report.inputs(), clean)
            for name in ("src/ignored_helper.py", "lib/ignored_helper.py", "tests/ignored_helper.py",
                         "tools/inspect_compiler/__init__.py", "tests/ignored_pkg/__init__.py",
                         "build/ref/compiler.py", "__pycache__/ignored_helper.py"):
                with self.subTest(source=name):
                    path = self.write(name, "value = 11\n")
                    self.assertFalse(report.clean_inputs(report.inputs()))
                    path.unlink()
                    self.assertEqual(report.inputs(), clean)

    def test_sidecars_and_internal_links_cover_helpers_outside_tests(self):
        helper = self.write("ports/fixture/value.py", "value = 11\n")
        sidecar = self.write("tests/probe.path", "ports/fixture\n")
        (self.root / "tests/alias.py").symlink_to("../ports/fixture/value.py")
        (self.root / "tests/pkg").symlink_to("../ports/fixture", target_is_directory=True)
        self.commit()
        with mock.patch.object(report, "ROOT", self.root):
            before = report.inputs()
            self.assertTrue(report.clean_inputs(before))
            helper.write_text("value = 29\n")
            self.assertFalse(report.clean_inputs(report.inputs()))
            self.commit()
            after = report.inputs()
            self.assertTrue(report.clean_inputs(after))
            self.assertNotEqual(before["corpus"]["digest"], after["corpus"]["digest"])
            with tempfile.TemporaryDirectory() as outside:
                external = Path(outside)
                (external / "value.py").write_text("value = 41\n")
                sidecar.write_text(outside + "\n")
                self.commit()
                self.assertFalse(report.clean_inputs(report.inputs()))
                sidecar.write_text("ports/fixture\n")
                self.commit()
                for name, target in (("tests/external.py", external / "value.py"),
                                     ("tests/external_pkg", external)):
                    with self.subTest(link=name):
                        link = self.root / name
                        link.symlink_to(target, target_is_directory=target.is_dir())
                        self.commit()
                        self.assertFalse(report.clean_inputs(report.inputs()))
                        link.unlink()
                        self.commit()
                self.assertFalse(report.clean_inputs(report.inputs([str(external / "value.py")])))
            self.assertTrue(report.clean_inputs(report.inputs()))

    def test_empty_namespace_and_host_platform_change_proof_inputs(self):
        program = self.write("tests/programs/core/namespace.py",
                             "try:\n    import ghost\nexcept ImportError:\n    print(1)\nelse:\n    print(2)\n")
        self.commit()
        _, absent = report.inspect(str(program), 120)
        with mock.patch.object(report, "ROOT", self.root):
            before = report.inputs()
            self.assertTrue(report.clean_inputs(before))
        namespace = program.parent / "ghost"
        namespace.mkdir()
        _, present = report.inspect(str(program), 120)
        self.assertNotEqual(absent, present)
        with mock.patch.object(report, "ROOT", self.root):
            self.assertFalse(report.clean_inputs(report.inputs()))
            self.write("tests/programs/core/ghost/anchor.txt", "tracked directory\n")
            self.commit()
            indexed = report.inputs()
            self.assertTrue(report.clean_inputs(indexed))
            self.assertNotEqual(before["corpus"]["digest"], indexed["corpus"]["digest"])
            (namespace / "anchor.txt").unlink()
            namespace.rmdir()
            self.assertNotEqual(report.inputs()["corpus"]["digest"], indexed["corpus"]["digest"])
            with mock.patch.object(report.sys, "platform", "other-host"):
                self.assertNotEqual(report.inputs()["compiler"]["digest"], before["compiler"]["digest"])
                output = self.root / "report.md"
                output.write_text(report.render(report.summarize([]), dict(META, inputs=before)))
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(report.status(output), 1)


class StatusTests(unittest.TestCase):
    def status(self, now):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "REPORT.md"
            path.write_text(report.render(report.summarize([record("a.py")]), META))
            with mock.patch.object(report, "inputs", return_value=now), mock.patch("builtins.print"):
                return report.status(path)

    def test_changed_or_uncommitted_inputs_are_stale(self):
        same = {group: dict(item, clean=True) for group, item in META["inputs"].items()}
        self.assertEqual(self.status(same), 0)
        self.assertEqual(self.status(dict(same, compiler={"digest": "d" * 16, "clean": True})), 1)
        self.assertEqual(self.status(dict(same, corpus=dict(same["corpus"], clean=False))), 1)

    def test_each_input_group_has_a_digest(self):
        self.assertIn("tools/lean_report.py", report.INPUTS["checkers"])
        found = report.inputs()
        self.assertEqual(set(found), set(report.INPUTS))
        self.assertTrue(all(len(item["digest"]) == 16 and type(item["clean"]) is bool for item in found.values()))


class CanonicalOutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.programs = ["tests/programs/core/first.py", "tests/programs/core/second.py"]
        for name in self.programs:
            self.write(name, "print(1)\n")
        self.write("tools/lean_boundary/lean-toolchain", "leanprover/lean4:v4.35.0\n")
        self.canonical = self.write("tools/lean_boundary/REPORT.md", "old full report\n")
        checker = self.write("checker", "checker bytes\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                        "commit", "-qm", "canonical report fixture"], cwd=self.root, check=True)
        self.args = ["--jobs", "1", "--checker", str(checker), "--access-checker", str(checker),
                     "--records", str(self.root / "records.jsonl")]
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.object(report, "ROOT", self.root))
        self.patches.enter_context(mock.patch.object(report, "REPORT", self.canonical))
        self.patches.enter_context(mock.patch.object(report.corpus, "corpus", return_value=self.programs))
        self.patches.enter_context(mock.patch.object(report.storage_corpus, "select", return_value=[]))
        self.checked = self.patches.enter_context(mock.patch.object(
            report, "check_program", side_effect=lambda program, *_: record(program)))
        self.patches.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.patches.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def alias(self):
        path = self.root / "alias.md"
        path.hardlink_to(self.canonical)
        return path

    def test_hard_link_cannot_write_partial_but_can_write_full_report(self):
        alias = self.alias()
        before = self.canonical.read_bytes()
        with self.assertRaises(SystemExit):
            report.main([self.programs[0], *self.args, "--output", str(alias)])
        self.assertEqual(self.canonical.read_bytes(), before)
        self.checked.assert_not_called()
        self.assertEqual(report.main([*self.args, "--output", str(alias)]), 0)
        self.assertEqual(self.checked.call_count, 2)
        self.assertEqual(report.recorded(self.canonical)["corpus"]["programs"], [])
        self.assertEqual(report.status(self.canonical), 0)

    def test_hard_link_cannot_render_partial_records_over_full_report(self):
        output = self.root / "partial.md"
        self.assertEqual(report.main([self.programs[0], *self.args, "--output", str(output)]), 0)
        alias = self.alias()
        before = self.canonical.read_bytes()
        with self.assertRaises(SystemExit):
            report.main([*self.args, "--render", "--output", str(alias)])
        self.assertEqual(self.canonical.read_bytes(), before)
        self.assertEqual(self.checked.call_count, 1)

    def test_canonical_status_rejects_copied_partial_selection(self):
        output = self.root / "partial.md"
        self.assertEqual(report.main([self.programs[0], *self.args, "--output", str(output)]), 0)
        self.assertEqual(report.status(output), 0)
        self.canonical.write_bytes(output.read_bytes())
        self.assertEqual(report.status(self.canonical), 1)
        self.assertEqual(report.status(self.alias()), 1)

    def test_interrupted_full_run_cannot_certify_a_copied_partial_render(self):
        # Exercise the real runner and JSONL writes, interrupting its second
        # program. Only the costly proof work uses fixture records.
        output = self.root / "interrupted.md"
        self.checked.side_effect = [record(self.programs[0]), KeyboardInterrupt]
        before = self.canonical.read_bytes()
        with self.assertRaises(KeyboardInterrupt):
            report.main(self.args)
        self.assertEqual(self.canonical.read_bytes(), before)
        header, records = report.load(self.root / "records.jsonl")
        self.assertEqual(header["inputs"]["corpus"]["programs"], [])
        self.assertEqual([r["program"] for r in records], self.programs[:1])
        self.assertEqual(report.main([*self.args, "--render", "--output", str(output)]), 0)
        self.canonical.write_bytes(output.read_bytes())
        self.assertEqual(report.status(self.canonical), 1)
        # Resume genuinely completes the missing program and restores status.
        self.checked.reset_mock(side_effect=True)
        self.checked.side_effect = lambda program, *_: record(program)
        self.assertEqual(report.main([*self.args, "--resume"]), 0)
        self.checked.assert_called_once()
        self.assertEqual(self.checked.call_args.args[0], self.programs[1])
        self.assertEqual(report.status(self.canonical), 0)

    def test_missing_duplicate_or_different_records_cannot_certify_full_corpus(self):
        self.assertEqual(report.main(self.args), 0)
        records_path = self.root / "records.jsonl"
        header, records = report.load(records_path)
        output = self.root / "historical.md"
        variants = (records[:1], [records[0], records[0]],
                    [records[0], dict(records[1], program="tests/programs/core/other.py")])
        for rows in variants:
            with self.subTest(programs=[r["program"] for r in rows]):
                records_path.write_text("\n".join(json.dumps(row) for row in [{"header": header}, *rows]) + "\n")
                self.assertEqual(report.main([*self.args, "--render", "--output", str(output)]), 0)
                self.canonical.write_bytes(output.read_bytes())
                self.assertEqual(report.status(self.canonical), 1)
        # Even matching expected/evaluated identities must name today's full
        # corpus, not merely the same number of different programs.
        wrong = dict(header, inventory=report.inventory(r["program"] for r in variants[-1]))
        self.canonical.write_text(report.render(report.summarize(variants[-1]), report.meta(wrong, variants[-1])))
        self.assertEqual(report.status(self.canonical), 1)

    def test_legacy_or_malformed_completion_does_not_certify_canonical_report(self):
        self.assertEqual(report.main(self.args), 0)
        original = self.canonical.read_text()
        completion = report.recorded_completion(self.canonical)
        marker = next(line for line in original.splitlines() if line.startswith(report.COMPLETION_MARK))
        bad = [None, {}, dict(completion, version=2), dict(completion, failed=False),
               dict(completion, expected=dict(completion["expected"], count=True)),
               dict(completion, evaluated=dict(completion["evaluated"], sha256="bad"))]
        for value in bad:
            with self.subTest(metadata=value):
                self.canonical.write_text(original.replace(marker,
                    report.COMPLETION_MARK + json.dumps(value) + " -->"))
                self.assertEqual(report.status(self.canonical), 1)
        for replacement in ("", report.COMPLETION_MARK + "{ -->", marker + "\n" + marker):
            with self.subTest(marker=replacement):
                self.canonical.write_text(original.replace(marker, replacement))
                self.assertEqual(report.status(self.canonical), 1)
        # Old records may still be rendered for investigation, but cannot be
        # resumed or copied into the canonical report as completed evidence.
        records_path = self.root / "records.jsonl"
        header, records = report.load(records_path)
        header.pop("inventory")
        records_path.write_text("\n".join(json.dumps(row) for row in [{"header": header}, *records]) + "\n")
        before = records_path.read_bytes()
        with self.assertRaises(SystemExit):
            report.main([*self.args, "--resume"])
        self.assertEqual(records_path.read_bytes(), before)
        output = self.root / "legacy.md"
        self.assertEqual(report.main([*self.args, "--render", "--output", str(output)]), 0)
        self.canonical.write_bytes(output.read_bytes())
        self.assertEqual(report.status(self.canonical), 1)

    def test_completed_proof_limitations_differ_from_incomplete_checks(self):
        limitations = row(2, 0, unproved=[item("@limited", "unsupported"), item("@unproved")])
        self.checked.side_effect = lambda program, *_: record(program, fields=limitations)
        self.assertEqual(report.main(self.args), 0)
        self.assertEqual(report.status(self.canonical), 0)
        incomplete = (dict(record(self.programs[1]), failed={"gc_check": "interrupted"}),
                      {"program": self.programs[1], "seconds": 1})
        for last in incomplete:
            with self.subTest(record=last):
                self.checked.side_effect = [record(self.programs[0]), last]
                self.assertEqual(report.main(self.args), 1)
                self.assertEqual(report.status(self.canonical), 1)

    def test_promoting_programs_need_their_conditional_checks(self):
        with mock.patch.object(report.storage_corpus, "select", return_value=self.programs[1:]):
            self.assertEqual(report.main(self.args), 1)
            self.assertEqual(report.status(self.canonical), 1)
            self.checked.side_effect = lambda program, *_: record(
                program, **({key: row(0, 0, 0) for key in ("int", "int_inline", "storage")}
                            if program == self.programs[1] else {}))
            self.assertEqual(report.main(self.args), 0)
            self.assertEqual(report.status(self.canonical), 0)
            # Altering the declared conditional inventory cannot make missing
            # checks certify a canonical report either.
            header, _ = report.load(self.root / "records.jsonl")
            header["promoting"] = []
            rows = [record(program) for program in self.programs]
            self.canonical.write_text(report.render(report.summarize(rows), report.meta(header, rows)))
            self.assertEqual(report.status(self.canonical), 1)


class WorkerTests(unittest.TestCase):
    PROGRAM = report.ROOT / "tools/lean_boundary/examples/generators.py"

    def test_one_worker_uses_the_same_checks_and_cache_without_a_pool(self):
        args = argparse.Namespace(jobs=1, start_method="forkserver", timeout=120,
                                  checker="boundary", access_checker="access")
        original = report._verdicts, report.guards._removal_attempts, report.boundary.RESULTS
        seen = []

        def checked(program, promoting, timeout, checker, access_checker):
            seen.append((program, promoting, timeout, checker, access_checker))
            self.assertIsInstance(report.boundary.RESULTS, report.Shared)
            key = ("checker", "candidate")
            if program == "first.py":
                report.boundary.RESULTS[key] = {"accepted": True}
            else:
                self.assertEqual(report.boundary.RESULTS[key], {"accepted": True})
            return record(program, fields=row(3, 3))

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(report.multiprocessing, "get_context", side_effect=AssertionError("no context")), \
                mock.patch.object(report.concurrent.futures, "ProcessPoolExecutor", side_effect=AssertionError("no pool")), \
                mock.patch.object(report, "check_program", side_effect=checked):
            database = report.results_database(Path(directory) / "results.db")
            records = list(report.checked_records(args, ["first.py", "second.py"], {"second.py"}, database))
        self.assertEqual(records, [record("first.py", fields=row(3, 3)), record("second.py", fields=row(3, 3))])
        self.assertEqual(seen, [("first.py", False, 120, "boundary", "access"),
                                ("second.py", True, 120, "boundary", "access")])
        for before, after in zip(original, (report._verdicts, report.guards._removal_attempts, report.boundary.RESULTS),
                                 strict=True):
            self.assertIs(before, after)

    def test_workers_share_each_result_by_its_kind_and_key(self):
        with tempfile.TemporaryDirectory() as directory:
            database = report.results_database(Path(directory) / "results.db")
            one, other, access = (report.Shared(database, kind) for kind in ("lean", "lean", "access"))
            key = ("/checker", "0" * 64)
            self.assertNotIn(key, other)
            one[key] = {"accepted": True, "nodes": 3, "payloads": 1}
            self.assertIn(key, other)
            self.assertEqual(other[key], {"accepted": True, "nodes": 3, "payloads": 1})
            self.assertIsNone(access.get(key))

    def test_a_forked_compilation_writes_the_snapshot_inspect_compiler_does(self):
        # (byte for byte: the records' digests and checks are the tool's own run's)
        _, digest = report.inspect(str(self.PROGRAM), 120)
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inspection"
            subprocess.run([sys.executable, str(report.ROOT / "tools/inspect_compiler.py"), str(self.PROGRAM),
                            "--output", str(output), "--typed-after-only", "--guard-evidence"],
                           env=dict(env, PYSTACHY_HOME=str(report.ROOT)), check=True, capture_output=True, timeout=120)
            self.assertEqual(digest, hashlib.sha256((output / "typed-after.json").read_bytes()).hexdigest())

    def test_a_rejected_program_and_a_compilation_past_its_time_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "rejected.py"
            program.write_text("x: int = 'one'\nprint(x)\n")
            with self.assertRaisesRegex(ValueError, "inspection rejected"):
                report.inspect(str(program), 120)
            output = Path(directory) / "late"
            output.mkdir()
            with self.assertRaises(subprocess.TimeoutExpired):
                report.compiled(self.PROGRAM, output, dict(os.environ), 0.01)


class CommittedReportTests(unittest.TestCase):
    def test_committed_report_has_every_check_and_its_inputs(self):
        text = report.REPORT.read_text()
        self.assertEqual(set(report.recorded()), set(report.INPUTS))
        for _, title, document, _ in report.CHECKS:
            self.assertIn(f"| [{title}]({document}) |", text)
            self.assertTrue((report.REPORT.parent / document.split("#")[0]).is_file(), document)


if __name__ == "__main__":
    unittest.main()
