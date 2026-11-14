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
