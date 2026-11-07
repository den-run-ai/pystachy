"""Optimization experiments must reject wrong witnesses and incompatible profiles."""
from collections import Counter
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


BENCH = Path(__file__).resolve().parents[1] / "bench/compiler_host"
sys.path.insert(0, str(BENCH))
SPEC = importlib.util.spec_from_file_location("pgo_experiment", BENCH / "profile_guided.py")
pgo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pgo)
SPEC = importlib.util.spec_from_file_location("bootstrap_policies", BENCH / "bootstrap_followup.py")
followup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(followup)


class FakeCommands:
    """Only artifact creation is simulated; main's evidence gates run unchanged."""

    def __init__(self, hook=None):
        self.results = []
        self.hook = hook

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, command, env, timeout):
        result = dict(command=command, exit_code=0, timed_out=False, cpu_s=0.25,
                      wall_s=0.5, sampled_process_tree_peak_rss_kib=1024, stdout="", stderr="")
        if "-o" in command:
            output = Path(command[command.index("-o") + 1])
            data = b"artifact\n"
            if command[1] in ("ir", "rt"):
                data = {"pystachy.py": b"self IR\n", "runtime.py": b"runtime IR\n",
                        "bench.py": b"json IR\n"}[Path(command[2]).name]
            output.write_bytes(data)
        if "LLVM_PROFILE_FILE" in env:
            Path(env["LLVM_PROFILE_FILE"].replace("%p", str(len(self.results)))).write_bytes(b"counts")
        self.results.append(result)
        if self.hook:
            self.hook(command, env, result)
        return result


class ExperimentFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-pgo-controls-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        (self.source / "bench/json_repair").mkdir(parents=True)
        (self.source / "ports").mkdir()
        for name in ("pystachy.py", "runtime.py", "runtime.c", "bench/json_repair/bench.py"):
            (self.source / name).write_text("frozen source\n")
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        for name, data in (("raw.ll", b"self IR\n"), ("seed-rt.ll", b"runtime IR\n"),
                           ("linked.bc", b"frozen linked bitcode\n")):
            (self.snapshot / name).write_bytes(data)
        self.baseline = self.root / "baseline"
        self.baseline.write_bytes(b"trusted compiler")
        self.runner = FakeCommands()
        self.report = self.root / "report.json"
        self.work = self.root / "work"

    def run_experiment(self):
        argv = ["profile_guided.py", "--snapshot", str(self.snapshot), "--source-root", str(self.source),
                "--baseline-compiler", str(self.baseline), "--llvm", str(self.root / "llvm"),
                "--work", str(self.work), "--report", str(self.report), "--policy", "pgo"]
        with patch.object(sys, "argv", argv), patch.object(pgo, "Commands", return_value=self.runner), \
             patch.object(pgo.bootstrap, "tool_identity", return_value={"clang": "fixed"}), \
             patch.object(pgo.bootstrap, "host_state", return_value={}), \
             patch.object(pgo, "profile_tool_identity", return_value={"profdata": "fixed"}), \
             contextlib.redirect_stdout(io.StringIO()):
            return pgo.main()


class ExperimentControls(ExperimentFixture):
    def test_success_and_backend_accounting(self):
        self.assertEqual(self.run_experiment(), 0)
        report = json.loads(self.report.read_text())
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["training"]), 2)
        self.assertEqual(set(report["builds"][0]["witnesses"]), {"self", "json-repair", "runtime"})
        self.assertEqual(report["builds"][0]["cpu_s"], 1)
        self.assertGreater(len(report["commands"]), len(report["builds"][0]["steps"]))

    def test_wrong_baseline_prevents_training(self):
        def corrupt(command, env, result):
            if command[0] == str(self.baseline):
                Path(command[-1]).write_bytes(b"wrong IR")
        self.runner.hook = corrupt
        with self.assertRaisesRegex(RuntimeError, "baseline"):
            self.run_experiment()
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["commands"]), 1)

    def test_wrong_candidate_witness_preserves_failure(self):
        def corrupt(command, env, result):
            if Path(command[0]).parent.name == "pgo-0":
                Path(command[-1]).write_bytes(b"wrong IR")
        self.runner.hook = corrupt
        with self.assertRaisesRegex(RuntimeError, "witness mismatch"):
            self.run_experiment()
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertFalse(report["builds"][0]["witnesses"]["self"]["matches"])

    def test_failed_optimizer_preserves_command_and_diagnostic(self):
        def fail(command, env, result):
            if any(arg.startswith("-fprofile-use=") for arg in command):
                result.update(exit_code=17, stderr="injected optimizer failure")
        self.runner.hook = fail
        with self.assertRaisesRegex(RuntimeError, "injected optimizer failure"):
            self.run_experiment()
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["commands"][-1]["exit_code"], 17)
        self.assertEqual(report["commands"][-1]["stderr"], "injected optimizer failure")

    def test_profile_drift_invalidates_completion(self):
        def mutate(command, env, result):
            if Path(command[0]).parent.name == "pgo-0" and command[1] == "rt":
                (self.work / "compiler.profdata").write_bytes(b"different profile")
        self.runner.hook = mutate
        self.assertEqual(self.run_experiment(), 1)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertFalse(report["profile_unchanged"])


class ProfileReuseControls(ExperimentFixture):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.run_experiment(), 0)
        self.prior = json.loads(self.report.read_text())

    def reuse(self):
        return pgo.reuse_profile(self.work / "compiler.profdata", self.report, self.prior["source"],
                                 self.prior["inputs"], self.prior["training_artifacts"], self.prior["llvm"],
                                 self.root / "copied.profdata", self.prior["profile_tools"])

    def test_copy_retains_measured_preparation_costs(self):
        reused = self.reuse()
        self.assertEqual(reused["instrumented_build"], self.prior["instrumented_build"])
        self.assertEqual(reused["training"], self.prior["training"])
        (self.work / "compiler.profdata").write_bytes(b"later modification")
        self.assertEqual(pgo.sha(self.root / "copied.profdata"), self.prior["profile_sha256"])

    def test_incomplete_incompatible_or_changed_training_is_rejected(self):
        cases = [(key, False) for key in ("complete", "source_unchanged", "inputs_unchanged",
                                          "training_inputs_unchanged", "baseline_unchanged")]
        cases += [(key, {}) for key in ("source", "inputs", "training_artifacts", "llvm", "profile_tools")]
        cases += [("profile_reuse", {"copied": True}), ("profile_sha256", "wrong"), ("training", [])]
        for changes in ({"matches": False}, {"exit_code": 1}, {"timed_out": True}):
            training = copy.deepcopy(self.prior["training"])
            training[0].update(changes)
            cases.append(("training", training))
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.report.write_text(json.dumps(dict(self.prior, **{key: value})))
                with self.assertRaises(ValueError):
                    self.reuse()
                self.assertFalse((self.root / "copied.profdata").exists())

    def test_changed_copy_is_rejected(self):
        def corrupt(source, destination):
            destination.write_bytes(b"different profile bytes")
        with patch.object(pgo.shutil, "copyfile", side_effect=corrupt), self.assertRaisesRegex(ValueError, "copying"):
            self.reuse()


class ScheduleControls(unittest.TestCase):
    def test_complete_rotations_balance_positions_and_neighbor_directions(self):
        for count in (1, 2, 3, 4):
            policies = list(range(count))
            orders = [pgo.scheduled(policies, sample) for sample in range(2 * count)]
            self.assertTrue(all(sorted(order) == policies for order in orders))
            for position in range(count):
                self.assertEqual(Counter(order[position] for order in orders), Counter({p: 2 for p in policies}))
            neighbors = Counter(pair for order in orders for pair in zip(order, order[1:]))
            self.assertTrue(all(amount == neighbors[b, a] for (a, b), amount in neighbors.items()))


class BootstrapPolicyControls(unittest.TestCase):
    def test_inline_policy_requires_supported_source_before_starting_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            driver = root / "src/pystachy_compiler/driver.py"
            driver.parent.mkdir(parents=True)
            # A marker in old source is not an implemented driver option.
            driver.write_text('# PYSTACHY_AOT_INLINE_THRESHOLD -inline-threshold=\ndef main():\n    pass\n')
            argv = ["bootstrap_followup.py", "--root", str(root), "--llvm", str(root / "llvm"),
                    "--work", str(root / "work"), "--report", str(root / "report.json"),
                    "--variant", "driver-o0", "--variant", "driver-inline75"]
            with patch.object(sys, "argv", argv), patch.object(followup, "Commands") as commands, \
                 contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as failure:
                followup.main()
            self.assertEqual(failure.exception.code, 2)
            self.assertIn("PYSTACHY_AOT_INLINE_THRESHOLD", error.getvalue())
            commands.assert_not_called()
            self.assertFalse((root / "work").exists())
            followup.require_inline_support(root, ["driver-o0"])
            driver.write_text('def aot_inline_flags():\n    value = "PYSTACHY_AOT_INLINE_THRESHOLD"\n'
                              '    return " -mllvm -inline-threshold=" + value\ndef main():\n    pass\n')
            with self.assertRaises(ValueError):
                followup.require_inline_support(root, ["driver-inline75"])
        followup.require_inline_support(BENCH.parents[1], ["driver-inline75"])

    @staticmethod
    def run_identity(policy, first="temporary", final="ordinary"):
        return {"policy": policy, "bootstrap": {"binaries": {
            "pystachy1": {"sha256": first}, "pystachy2": {"sha256": final}}}}

    def test_inline_pair_requires_identical_temporary_compilers(self):
        policies = ["driver-o0", "driver-inline75"]
        baseline = self.run_identity(policies[0])
        candidate = self.run_identity(policies[1], final="different-final")
        checked = followup.compiler_identity([baseline, candidate], policies)
        self.assertTrue(checked["compiler_identity_passed"])
        self.assertTrue(checked["driver_stage1_identity_required"])
        self.assertTrue(checked["driver_stage1_compilers_identical"])
        self.assertEqual(checked["driver_stage1_sha256"], {policy: ["temporary"] for policy in policies})
        candidate["bootstrap"]["binaries"]["pystachy1"]["sha256"] = "changed-temporary"
        checked = followup.compiler_identity([baseline, candidate], policies)
        self.assertFalse(checked["compiler_identity_passed"])
        self.assertFalse(checked["driver_stage1_compilers_identical"])
        self.assertFalse(followup.compiler_identity([baseline], policies)["compiler_identity_passed"])

    def test_changed_final_does_not_waive_ordinary_final_identity(self):
        runs = [self.run_identity("driver-o0"), self.run_identity("split-o0", final="changed-ordinary"),
                self.run_identity("driver-inline75", final="opt-in-final")]
        checked = followup.compiler_identity(runs, [run["policy"] for run in runs])
        self.assertFalse(checked["compiler_identity_passed"])
        self.assertFalse(checked["ordinary_final_compilers_identical"])

    def test_runtime_overlap_requires_both_compilers_to_match(self):
        policies = ["driver-o0", "driver-overlap"]
        for first, final, passed in (("temporary", "ordinary", True),
                                     ("different", "ordinary", False),
                                     ("temporary", "different", False)):
            with self.subTest(first=first, final=final):
                runs = [self.run_identity(policies[0]), self.run_identity(policies[1], first, final)]
                checked = followup.compiler_identity(runs, policies)
                self.assertEqual(checked["compiler_identity_passed"], passed)
                self.assertTrue(checked["final_identity_required"])
                self.assertTrue(checked["driver_stage1_identity_required"])

    def test_thinlto_comparison_keeps_the_same_temporary_compiler(self):
        runs = [self.run_identity("driver-o0"), self.run_identity("driver-inline75", final="inline"),
                self.run_identity("driver-thinlto4", final="thinlto")]
        policies = [run["policy"] for run in runs]
        checked = followup.compiler_identity(runs, policies)
        self.assertTrue(checked["compiler_identity_passed"])
        self.assertTrue(checked["driver_stage1_compilers_identical"])
        runs[-1] = self.run_identity("driver-thinlto4", first="changed", final="thinlto")
        self.assertFalse(followup.compiler_identity(runs, policies)["compiler_identity_passed"])

    def test_future_explicit_backend_can_change_final_without_inline_gate(self):
        future = "driver-future-backend"
        with patch.dict(followup.POLICIES, {future: ["--future-backend", "4"]}), \
             patch.object(followup, "CHANGED_FINAL", followup.CHANGED_FINAL | {future}):
            followup.require_inline_support(Path("/unused/source"), [future])
            runs = [self.run_identity("driver-o0"), self.run_identity(future, "other-stage1", "other-final")]
            checked = followup.compiler_identity(runs, ["driver-o0", future])
        self.assertTrue(checked["compiler_identity_passed"])
        self.assertFalse(checked["driver_stage1_identity_required"])
        self.assertIsNone(checked["driver_stage1_compilers_identical"])


@unittest.skipUnless(os.environ.get("PYSTACHY_TEST_LLVM"), "set PYSTACHY_TEST_LLVM for IR-PGO diagnostics")
class RealProfileDiagnostics(unittest.TestCase):
    def test_strict_ir_policy_rejects_missing_and_mismatched_profiles(self):
        llvm = Path(os.environ["PYSTACHY_TEST_LLVM"])
        environment = {k: v for k, v in os.environ.items() if not k.startswith("LLVM_PROFILE_")}
        with tempfile.TemporaryDirectory(prefix="pystachy-pgo-diagnostics-") as directory:
            work = Path(directory)
            base = "define i32 @main() {\n  ret i32 0\n}\n"
            source = work / "input.ll"
            source.write_text(base)
            def run(tool, *args, check=True):
                return subprocess.run([str(llvm / tool), *map(str, args)], env=environment,
                                      capture_output=True, text=True, timeout=30, check=check)
            run("clang", "-O2", "-fprofile-generate", source, "-o", work / "instrumented")
            subprocess.run([str(work / "instrumented")], check=True, timeout=10,
                           env=dict(environment, LLVM_PROFILE_FILE=str(work / "profile.profraw")))
            run("llvm-profdata", "merge", "-o", work / "profile.profdata", work / "profile.profraw")
            cases = ((base, None),
                     (base + "define i32 @extra() noinline { ret i32 7 }\n", "no profile data"),
                     ("declare i32 @getchar()\ndeclare void @one()\ndeclare void @two()\n"
                      "define i32 @main() {\n %x = call i32 @getchar()\n %y = icmp sgt i32 %x, 42\n"
                      " br i1 %y, label %a, label %b\na:\n call void @one()\n ret i32 0\n"
                      "b:\n call void @two()\n ret i32 0\n}\n", "hash mismatch"))
            for text, diagnostic in cases:
                with self.subTest(diagnostic=diagnostic):
                    source.write_text(text)
                    result = run("clang", "-O2", f"-fprofile-use={work / 'profile.profdata'}",
                                 *pgo.STRICT_PROFILE, "-c", "-emit-llvm", source, "-o", work / "output.bc", check=False)
                    self.assertEqual(result.returncode == 0, diagnostic is None, result.stderr)
                    if diagnostic:
                        self.assertIn(diagnostic, result.stderr)


if __name__ == "__main__":
    unittest.main()
