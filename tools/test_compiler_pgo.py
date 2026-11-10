"""PGO evidence must fail closed without requiring LLVM or a compiler build."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compiler_pgo", ROOT / "bench/compiler_pgo/prototype.py")
pgo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pgo)


@unittest.skipUnless(sys.platform == "linux" and hasattr(os, "sched_getaffinity") and hasattr(os, "wait4"),
                     "the PGO experiment requires Linux affinity and wait4")
class CompilerPgoGates(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy pgo gates ")
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.out = base / "evidence"
        self.out.mkdir()
        for _, _, name in pgo.TRAINING + pgo.HOLDOUT:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("pass\n")
        (self.repo / "ports").mkdir()
        (self.repo / "ports/tracked.py").write_text("pass\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "-qm", "fixture")

        # Exercise the evidence methods with real files/processes while avoiding
        # constructor discovery of a system LLVM toolchain.
        self.experiment = object.__new__(pgo.Experiment)
        self.experiment.repo = self.repo
        self.experiment.out = self.out
        self.experiment.llvm = base / "unused-llvm"
        self.experiment.manifest_path = self.out / "manifest.json"
        self.experiment.env = dict(os.environ)
        self.experiment.cpu = min(os.sched_getaffinity(0))
        self.experiment.data = {"commands": [], "checks": {}}
        self.experiment.source = self.experiment.source_identity()
        for variant in ("ordinary", "instrumented", "pgo"):
            (self.out / variant).write_bytes(variant.encode())
        self.experiment.data["ordinary_binary_sha256"] = pgo.digest(self.out / "ordinary")
        for variant in ("instrumented", "pgo"):
            self.experiment.data[variant + "_binary"] = {"sha256": pgo.digest(self.out / variant)}
        (self.out / "compiler.profdata").write_bytes(b"profile")
        self.experiment.data["profile"] = {"sha256": pgo.digest(self.out / "compiler.profdata")}
        (self.out / "compiler-linked.bc").write_bytes(b"linked bitcode")
        self.experiment.data["linked_bitcode_sha256"] = pgo.digest(self.out / "compiler-linked.bc")
        self.mark_verified()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def mark_verified(self):
        labels = [label + "-pgo-equality" for label, _, _ in pgo.TRAINING + pgo.HOLDOUT]
        labels += ["pgo-compiler-fixed-point", "pgo-runtime-fixed-point"]
        self.experiment.data["checks"] = {label: {"equal": True} for label in labels}
        self.experiment.data["verified_binaries"] = {
            variant: pgo.digest(self.out / variant) for variant in ("ordinary", "pgo")}
        self.experiment.flush()

    def test_complete_evidence_accepts_exact_binary_and_profile_bytes(self):
        self.assertEqual(self.experiment.verified_identity(),
                         self.experiment.data["verified_binaries"])

    def test_both_measurements_reject_missing_failed_or_changed_evidence(self):
        original = copy.deepcopy(self.experiment.data)
        corruptions = ("unverified", "wrong-binary-record", "missing-check", "failed-check",
                       "changed-binary", "changed-profile")
        for phase in ("measure", "memory"):
            for corruption in corruptions:
                with self.subTest(phase=phase, corruption=corruption):
                    self.experiment.data = copy.deepcopy(original)
                    (self.out / "pgo").write_bytes(b"pgo")
                    (self.out / "compiler.profdata").write_bytes(b"profile")
                    if corruption == "unverified":
                        del self.experiment.data["verified_binaries"]
                    elif corruption == "wrong-binary-record":
                        self.experiment.data["verified_binaries"]["pgo"] = "other binary"
                    elif corruption == "missing-check":
                        del self.experiment.data["checks"]["pgo-runtime-fixed-point"]
                    elif corruption == "failed-check":
                        self.experiment.data["checks"]["json-repair-pgo-equality"]["equal"] = False
                    elif corruption == "changed-binary":
                        (self.out / "pgo").write_bytes(b"different binary")
                    else:
                        (self.out / "compiler.profdata").write_bytes(b"different profile")
                    with patch.object(self.experiment, "run") as run, self.assertRaises(RuntimeError):
                        getattr(self.experiment, phase)()
                    run.assert_not_called()

    def test_untracked_port_and_tracked_source_drift_are_rejected(self):
        extra = self.repo / "ports/local.py"
        extra.write_text("pass\n")
        with self.assertRaisesRegex(RuntimeError, "Untracked compiler/runtime inputs: ports/local.py"):
            self.experiment.source_identity()
        extra.unlink()
        (self.repo / "ports/tracked.py").write_text("print('changed')\n")
        with self.assertRaisesRegex(RuntimeError, "input changed during the phase"):
            self.experiment.unchanged_sources()

    def test_exit_zero_must_produce_fresh_nonempty_output(self):
        output = self.out / "candidate.ll"
        for script in ("pass", "import pathlib, sys; pathlib.Path(sys.argv[1]).write_bytes(b'')"):
            with self.subTest(script=script):
                output.write_bytes(b"stale successful IR\n")
                with self.assertRaisesRegex(RuntimeError, "missing or empty output"):
                    self.experiment.run("no-output", [sys.executable, "-c", script, str(output)],
                                        outputs=(output,))
                self.assertTrue(not output.exists() or output.read_bytes() == b"")
                self.assertEqual(self.experiment.data["commands"][-1]["returncode"], 0)
        self.experiment.run("fresh-output", [sys.executable, "-c",
                            "import pathlib, sys; pathlib.Path(sys.argv[1]).write_bytes(b'fresh IR')", str(output)],
                            outputs=(output,))
        self.assertEqual(output.read_bytes(), b"fresh IR")

    def test_failed_process_retains_exit_status_and_diagnostic(self):
        with self.assertRaisesRegex(RuntimeError, "exit 7"):
            self.experiment.run("failed", [sys.executable, "-c",
                                "import sys; sys.stderr.write('deliberate failure'); sys.exit(7)"])
        record = json.loads(self.experiment.manifest_path.read_text())["commands"][-1]
        self.assertEqual(record["returncode"], 7)
        self.assertEqual(Path(record["stderr"]).read_text(), "deliberate failure")

    def test_comparison_rejects_different_or_empty_ir_and_records_failure(self):
        left, right = self.out / "left.ll", self.out / "right.ll"
        left.write_bytes(b"expected IR\n")
        right.write_bytes(left.read_bytes())
        self.experiment.compare("probe", left, right)
        self.assertTrue(self.experiment.data["checks"]["probe"]["equal"])
        for wanted, actual in ((b"expected IR\n", b"changed IR\n"), (b"", b"")):
            left.write_bytes(wanted)
            right.write_bytes(actual)
            with self.assertRaisesRegex(RuntimeError, "Output changed"):
                self.experiment.compare("probe", left, right)
            record = json.loads(self.experiment.manifest_path.read_text())["checks"]["probe"]
            self.assertFalse(record["equal"])

    def test_changed_bitcode_and_profile_warnings_stop_optimization(self):
        (self.out / "compiler-linked.bc").write_bytes(b"changed bitcode")
        with patch.object(self.experiment, "run") as run, self.assertRaisesRegex(RuntimeError, "bitcode drift"):
            self.experiment.build("pgo")
        run.assert_not_called()
        (self.out / "compiler-linked.bc").write_bytes(b"linked bitcode")
        diagnostic = self.out / "warning.err"
        diagnostic.write_text("warning: profile data may be out of date\n")
        with patch.object(self.experiment, "run", return_value={"stderr": str(diagnostic)}) as run:
            with self.assertRaisesRegex(RuntimeError, "Unexpected optimization diagnostic"):
                self.experiment.build("pgo")
        self.assertEqual(run.call_count, 1)

    def test_stale_training_profiles_are_never_merged(self):
        raw = self.out / "raw"
        raw.mkdir()
        (raw / "old.profraw").write_bytes(b"old counters")
        with patch.object(self.experiment, "run") as run, self.assertRaisesRegex(RuntimeError, "stale training profiles"):
            self.experiment.train()
        run.assert_not_called()

    def verification_fixture(self, *, skip_output=False):
        ir = b"; fixture IR\n"
        (self.repo / "build").mkdir()
        for name in ("stage1.ll", "rt1.ll"):
            (self.repo / "build" / name).write_bytes(ir)
        oracle = self.out / "oracle"
        oracle.mkdir()
        self.experiment.data["oracle"] = {}
        for label, _, _ in pgo.TRAINING + pgo.HOLDOUT:
            (oracle / (label + ".ll")).write_bytes(ir)
            self.experiment.data["oracle"][label] = pgo.digest(oracle / (label + ".ll"))
            (self.out / (label + ".pgo.ll")).write_bytes(ir)
        compiler = self.out / "pgo"
        compiler.write_text(f"#!{sys.executable}\nimport pathlib, sys\n"
                            + ("if sys.argv[2].endswith('/templates.py'): sys.exit(0)\n" if skip_output else "")
                            + f"pathlib.Path(sys.argv[-1]).write_bytes({ir!r})\n")
        compiler.chmod(0o755)
        self.experiment.data["pgo_binary"]["sha256"] = pgo.digest(compiler)
        self.mark_verified()

    def test_successful_verification_publishes_complete_evidence(self):
        self.verification_fixture()
        self.experiment.verify()
        self.assertEqual(self.experiment.verified_identity(),
                         self.experiment.data["verified_binaries"])

    def test_failed_reverification_cannot_reuse_old_ir_or_success_marker(self):
        self.verification_fixture(skip_output=True)
        with self.assertRaisesRegex(RuntimeError, "generics-pgo: missing or empty output"):
            self.experiment.verify()
        self.assertFalse((self.out / "generics.pgo.ll").exists())
        recorded = json.loads(self.experiment.manifest_path.read_text())
        self.assertNotIn("verified_binaries", recorded)
        with patch.object(self.experiment, "run") as run, self.assertRaisesRegex(RuntimeError, "Run verify"):
            self.experiment.measure()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
