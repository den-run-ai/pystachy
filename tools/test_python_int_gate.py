"""Fail-closed controls for the python-int compatibility release gate."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import python_int_gate as gate
import python_int_optin as exploratory

A = "tests/programs/sample/a.py"
B = "tests/programs/sample/b.py"
DIAGNOSTIC = A + ":2: error: unsupported storage boundary"
ISSUE = "https://github.com/den-run-ai/pystachy/issues/907"


def manifest_row(case=A, mode="jit"):
    return {"case": case, "mode": mode, "category": "unsupported-storage",
            "diagnostic": DIAGNOSTIC, "reason": "The annotated optional list stores checked int64 elements.",
            "issue": ISSUE}


def fixture(root, entries=()):
    root.mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for case in (A, B):
        path = root / case
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("print(1)\n")
        path.with_suffix(".out").write_text("1\n[exit 0]\n")
    (root / "tools").mkdir(exist_ok=True)
    (root / gate.MANIFEST).write_text(json.dumps({"schema": 1, "exceptions": list(entries)}))
    (root / ".python-version").write_text(".".join(map(str, sys.version_info[:3])) + "\n")
    (root / "tests/corpus.sh").write_text("corpus() { printf '%s\\n' " + A + " " + B + "; }\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)


def report(root, index=0, count=1):
    corpus = gate.programs(root)
    selected = corpus[index::count]
    allowed = gate.exceptions(root, corpus)
    rows = [{"case": case, "mode": mode, "result": "expected-failure" if (case, mode) in allowed else "pass",
             "diagnostic": allowed[(case, mode)]["diagnostic"] if (case, mode) in allowed else ""}
            for case in selected for mode in gate.MODES]
    return {"schema": 1, "kind": "python-int-gate", "pragma": "# pystachy: python-int",
            "python": (root / ".python-version").read_text().strip(), "compiler_sha256": "a" * 64,
            "source_sha256": gate.source_digest(root), "corpus_cases": len(corpus),
            "corpus_sha256": gate.optin.corpus_digest(root, corpus),
            "exceptions_sha256": gate.sha256(root / gate.MANIFEST), "shard_index": index, "shard_count": count,
            "gc_stress": False, "modes": list(gate.MODES), "cases": selected, "subset": False,
            "oracle_cases": len(selected), "expected_checks": len(rows), "completed_checks": len(rows),
            "passed_checks": sum(row["result"] == "pass" for row in rows),
            "expected_failures": sum(row["result"] == "expected-failure" for row in rows),
            "failures": [], "results": rows}


class ManifestTests(unittest.TestCase):
    def test_exact_classified_compiler_rejections_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, [manifest_row()])
            self.assertEqual(gate.exceptions(root, [A, B])[(A, "jit")], manifest_row())
            invalid = [
                {**manifest_row(), "category": "crash"},
                {**manifest_row(), "diagnostic": "OverflowError: Python int too large"},
                {**manifest_row(), "diagnostic": DIAGNOSTIC + "\nextra"},
                {**manifest_row(), "reason": ""},
                {**manifest_row(), "issue": "https://example.com/907"},
                {**manifest_row(), "case": "tests/programs/missing.py"},
                {**manifest_row(), "mode": "anything"},
                {**manifest_row(), "ignored": True},
            ]
            for row in invalid:
                with self.subTest(row=row):
                    (root / gate.MANIFEST).write_text(json.dumps({"schema": 1, "exceptions": [row]}))
                    with self.assertRaises(ValueError):
                        gate.exceptions(root, [A, B])
            (root / gate.MANIFEST).write_text(json.dumps({"schema": 1, "exceptions": [manifest_row(), manifest_row()]}))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                gate.exceptions(root, [A, B])
            (root / gate.MANIFEST).write_text('{"schema":1,"schema":1,"exceptions":[]}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                gate.exceptions(root, [A, B])


class IdentityTests(unittest.TestCase):
    def test_untracked_ignored_support_sources_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            (root / "lib").mkdir()
            (root / ".gitignore").write_text("lib/local.py\n")
            before = gate.source_digest(root)
            helper = root / "lib/local.py"
            helper.write_text("value = 1\n")
            added = gate.source_digest(root)
            self.assertNotEqual(before, added)
            helper.write_text("value = 2\n")
            self.assertNotEqual(added, gate.source_digest(root))
            helper.unlink()
            self.assertEqual(before, gate.source_digest(root))
            (root / "build").mkdir()
            (root / "build/report.json").write_text("{}\n")
            (root / "lib/__pycache__").mkdir()
            (root / "lib/__pycache__/local.pyc").write_bytes(b"generated")
            self.assertEqual(before, gate.source_digest(root))

    def test_directory_links_cannot_hide_external_or_ignored_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            fixture(root)
            (root / "lib").mkdir()
            external = Path(tmp) / "outside"
            external.mkdir()
            (external / "__init__.py").write_text("value = 1\n")
            link = root / "lib/extra"
            for target in (external, root / "build"):
                target.mkdir(exist_ok=True)
                link.symlink_to(target, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "directory link"):
                    gate.source_digest(root)
                link.unlink()
            # Internal fixture links stay supported, and both their target code and the
            # link itself participate even when neither has been added to the index.
            package = root / "tests/helpers"
            package.mkdir()
            source = package / "__init__.py"
            source.write_text("value = 1\n")
            before = gate.source_digest(root)
            link.symlink_to(package, target_is_directory=True)
            linked = gate.source_digest(root)
            self.assertNotEqual(before, linked)
            source.write_text("value = 2\n")
            self.assertNotEqual(linked, gate.source_digest(root))

    def test_tracked_source_mode_and_link_targets_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            path = root / A
            before = gate.source_digest(root)
            path.chmod(0o755)
            self.assertNotEqual(before, gate.source_digest(root))
            path.chmod(0o644)
            self.assertEqual(before, gate.source_digest(root))
            path.write_text("print(2)\n")
            self.assertNotEqual(before, gate.source_digest(root))


class ReportTests(unittest.TestCase):
    def test_full_reports_and_each_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, [manifest_row()])
            for index, count in ((0, 1), (0, 2), (1, 2)):
                gate.validate_report(report(root, index, count), root)

    def test_rejects_incomplete_stale_or_fabricated_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, [manifest_row()])
            good = report(root)
            mutations = {
                "subset": True, "modes": ["jit"], "gc_stress": True, "schema": True,
                "python": "0.0.0", "kind": "exploratory", "pragma": "# pystachy: dynamic-any",
                "corpus_cases": 1, "corpus_sha256": "0" * 64, "source_sha256": "0" * 64,
                "exceptions_sha256": "0" * 64, "compiler_sha256": "", "cases": [A],
                "shard_index": 1, "shard_count": 0, "oracle_cases": 1, "expected_checks": 3,
                "completed_checks": 3, "passed_checks": 4, "expected_failures": 0,
                "failures": ["a timeout"], "results": good["results"][:-1],
            }
            for field, value in mutations.items():
                with self.subTest(field=field), self.assertRaises(ValueError):
                    gate.validate_report({**good, field: value}, root)
            for changed in (
                [{**good["results"][0], "result": "pass", "diagnostic": ""}, *good["results"][1:]],
                [{**good["results"][0], "diagnostic": DIAGNOSTIC + " changed"}, *good["results"][1:]],
                [good["results"][0], good["results"][0], *good["results"][2:]],
                [*good["results"][:-1], {**good["results"][-1], "result": "expected-failure"}],
            ):
                with self.subTest(rows=changed), self.assertRaises(ValueError):
                    gate.validate_report({**good, "results": changed}, root)
            (root / "tools/new_helper.py").write_text("value = 1\n")
            with self.assertRaisesRegex(ValueError, "identity"):
                gate.validate_report(good, root)


class DiagnosticTests(unittest.TestCase):
    def test_only_existing_filename_under_exact_checkout_prefix_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            source = root / "lib/operator.py"
            source.parent.mkdir(parents=True)
            source.write_text("pass\n")
            diagnostic = str(source) + ":176: error: integer is unsupported"
            self.assertEqual(gate.normalize_diagnostic(diagnostic, root),
                             "lib/operator.py:176: error: integer is unsupported")
            unchanged = [
                "lib/operator.py:176: error: integer is unsupported",
                str(root) + "-other/lib/operator.py:176: error: integer is unsupported",
                str(root) + "/../repo/lib/operator.py:176: error: integer is unsupported",
                str(root) + "/missing.py:176: error: integer is unsupported",
                "elsewhere.py:176: error: " + str(source),
                diagnostic + "\nadditional error",
            ]
            for value in unchanged:
                with self.subTest(value=value):
                    self.assertEqual(gate.normalize_diagnostic(value, root), value)
            # A path mentioned in error text is never rewritten.
            text = diagnostic + " " + str(root) + "/another.py"
            self.assertEqual(gate.normalize_diagnostic(text, root),
                             "lib/operator.py:176: error: integer is unsupported " + str(root) + "/another.py")


class ExecutionTests(unittest.TestCase):
    def run_one(self, root, *, native_status=b"1\n", native_out=b"", native_error=None,
                base_ok=True, oracle_ok=True, pass_now=False, gc_stress=False, absolute_error=False, trace_error=None):
        overlay, temp = root / "overlay", root / "work"
        overlay.mkdir()
        (overlay / A).parent.mkdir(parents=True)
        (overlay / A).write_text("print(1)\n")
        (overlay / A).with_suffix(".out").write_text("stale\n[exit 0]\n")
        temp.mkdir()
        if absolute_error:
            (root / A).parent.mkdir(parents=True)
            (root / A).write_text("print(1)\n")
            native_error = (str(root) + "/" + DIAGNOSTIC + "\n").encode()
        diagnostic = DIAGNOSTIC if native_error is None else native_error.decode().rstrip("\n")
        output = ("selected 1 cases\n1 passed, 0 failed\n" if pass_now else
                  f"FAIL a (jit)\n  stderr:\n{diagnostic}\nselected 1 cases\n0 passed, 1 failed\n")

        def run(command, cwd, env, timeout):
            self.assertEqual(env["PYSTACHY_CACHE"], str(temp / "cache"))
            self.assertEqual(env["PYSTACHY_GC_STRESS_PROGRAM"], "1" if gc_stress else "0")
            if command[1] == "tests/record.sh":
                self.assertFalse((overlay / A).with_suffix(".out").exists())
                if oracle_ok:
                    (overlay / A).with_suffix(".out").write_text("1\n[exit 0]\n")
                return (0, "a: [exit 0]\n") if oracle_ok else (1, "oracle failed")
            if cwd == overlay:
                trace = temp / Path(A).with_suffix("") / "jit.status"
                trace.write_bytes(native_status)
                trace.with_suffix(".stdout").write_bytes(native_out)
                error = (DIAGNOSTIC + "\n").encode() if native_error is None else native_error
                trace.with_suffix(".stderr").write_bytes(error if trace_error is None else trace_error)
                return (0 if pass_now else 1), output
            return (0, "selected 1 cases\n1 passed, 0 failed\n") if base_ok else (1, "bad baseline")

        with mock.patch.object(gate.optin, "run", side_effect=run):
            result = gate.one(A, root, overlay, temp, "true", ["jit"], 1, {(A, "jit"): manifest_row()}, gc_stress)
        evidence = json.loads((temp / Path(A).with_suffix("") / "evidence.json").read_text())
        return result, evidence

    def test_expected_rejection_preserves_same_invocation_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, evidence = self.run_one(Path(tmp), gc_stress=True)
        self.assertEqual(result["results"][0]["result"], "expected-failure")
        self.assertEqual(evidence["modes"][0]["compiler_status"], "1\n")
        self.assertEqual(evidence["modes"][0]["baseline"]["status"], 0)

    def test_checkout_diagnostic_is_portable_but_raw_stderr_proof_stays_exact(self):
        for dirname in ("first-checkout", "different-checkout"):
            with self.subTest(dirname=dirname), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / dirname
                root.mkdir()
                result, evidence = self.run_one(root, absolute_error=True)
                self.assertEqual(result["results"][0]["result"], "expected-failure")
                self.assertEqual(result["results"][0]["diagnostic"], DIAGNOSTIC)
                self.assertEqual(evidence["modes"][0]["compiler_stderr"], str(root) + "/" + DIAGNOSTIC + "\n")
        for changed in ({"native_status": b"139\n"}, {"trace_error": (DIAGNOSTIC + "\n").encode()}):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                result, _ = self.run_one(Path(tmp), absolute_error=True, **changed)
                self.assertEqual(result["results"][0]["result"], "fail")

    def test_crash_timeout_duplicate_invocation_extra_output_and_bad_baseline_fail(self):
        for changes in ({"native_status": b"139\n"}, {"native_status": b"124\n"},
                        {"native_status": b"1\n1\n"}, {"native_out": b"side effect\n"},
                        {"native_error": (DIAGNOSTIC + "\nadditional failure\n").encode()},
                        {"native_error": (DIAGNOSTIC + " changed\n").encode()},
                        {"base_ok": False}, {"pass_now": True}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                result, _ = self.run_one(Path(tmp), **changes)
                self.assertEqual(result["results"][0]["result"], "fail")

    def test_oracle_failure_cannot_reuse_stale_recording(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, evidence = self.run_one(Path(tmp), oracle_ok=False)
        self.assertFalse(result["oracle"])
        self.assertEqual(result["results"], [])
        self.assertEqual(evidence["oracle"]["status"], 1)
        self.assertEqual(evidence["modes"], [])

    def test_nonexception_preserves_dev_full_for_jit_program(self):
        # Execute actual shell redirects: capturing the compiler's stdout first would
        # make the write succeed, even though the caller redirects it to /dev/full.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            compiler = root / "compiler.sh"
            compiler.write_text("#!/bin/sh\nprintf 'program output\\n' 2>/dev/null\nexit $?\n")
            compiler.chmod(0o755)
            overlay, work = root / "overlay", root / "work"
            gate.optin.prepare_tree(root, overlay, [A], gate.PRAGMA)
            work.mkdir()
            (root / "tests/record.sh").write_text(
                "printf 'expected\\n[exit 0]\\n' > tests/programs/sample/a.out\nprintf 'a: [exit 0]\\n'\n")
            (root / "tests/run.sh").write_text(
                'eval "$1 run $3" >/dev/full 2>/dev/null\nstatus=$?\n'
                'if [ "$status" -eq 0 ]; then\n'
                "  printf 'FAIL a (jit)\\nselected 1 cases\\n0 passed, 1 failed\\n'\n  exit 1\nfi\n"
                "printf 'selected 1 cases\\n1 passed, 0 failed\\n'\n")
            # prepare_tree copied tests before writing the minimal shell harnesses.
            for name in ("record.sh", "run.sh"):
                (overlay / "tests" / name).write_bytes((root / "tests" / name).read_bytes())
            result = gate.one(A, root, overlay, work, str(compiler), ["jit"], 5, {})
            self.assertEqual(result["results"][0]["result"], "pass")

    def test_exploratory_entry_can_only_forward_gate_explicitly(self):
        with mock.patch.object(gate, "main", return_value=42) as main:
            self.assertEqual(exploratory.main(["--gate", "--report", "gate.json"]), 42)
            main.assert_called_once_with(["--report", "gate.json"])


class MainTests(unittest.TestCase):
    def execute(self, tmp, change=None):
        root = Path(tmp)
        fixture(root)
        compiler = root / "compiler"
        compiler.write_text("#!/bin/sh\nexit 0\n")
        compiler.chmod(0o755)
        output = root / "build/report.json"

        def one(case, *args):
            rows = [{"case": case, "mode": mode, "result": "pass", "diagnostic": ""} for mode in gate.MODES]
            result = {"case": case, "oracle": True, "results": rows}
            if change is not None and case == B:
                change(result, root, compiler)
            return result

        with mock.patch.object(gate, "ROOT", root), mock.patch.object(gate, "one", side_effect=one), \
             mock.patch.object(gate.optin, "run", return_value=(0, "")), mock.patch("sys.stdout"):
            status = gate.main(["--compiler", str(compiler), "--report", str(output)])
        return status, json.loads(output.read_text())

    def test_complete_success_and_fail_closed_on_incomplete_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, result = self.execute(tmp)
        self.assertFalse(status)
        self.assertEqual((result["completed_checks"], result["passed_checks"]), (4, 4))
        def source_changed(result, root, compiler):
            (root / "lib").mkdir()
            (root / "lib/untracked.py").write_text("value = 1\n")

        changes = [
            lambda result, root, compiler: result["results"].pop(),
            lambda result, root, compiler: result["results"].reverse(),
            lambda result, root, compiler: result.update(oracle=False, results=[], failure="oracle failure"),
            source_changed,
            lambda result, root, compiler: compiler.write_text("#!/bin/sh\nexit 1\n"),
        ]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                status, result = self.execute(tmp, change)
                self.assertTrue(status)
                self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()
