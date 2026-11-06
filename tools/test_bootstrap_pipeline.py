"""Bootstrap scheduler controls with an executable, deliberately fallible compiler."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("bootstrap_pipeline.py")
SPEC = importlib.util.spec_from_file_location("bootstrap_pipeline", SCRIPT)
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)

FAKE = r'''
import json, os, pathlib, subprocess, sys, time
root = pathlib.Path.cwd()
argv = sys.argv[1:]
kind = argv[0]
out = pathlib.Path(argv[argv.index("-o") + 1])
name = out.stem
event = {"kind": kind, "name": name, "producer": pathlib.Path(sys.argv[0]).name,
         "opt": os.environ["PYSTACHY_AOT_OPT"], "jobs": int(os.environ["PYSTACHY_BUILD_JOBS"]),
         "partitions": int(os.environ["PYSTACHY_LTO_PARTITIONS"]), "begin": time.monotonic()}
with (root / "events.jsonl").open("a") as f:
    f.write(json.dumps(event) + "\n")
if os.getenv("RENDEZVOUS") == "1" and name in ("pystachy1", "rt1"):
    (root / ("ready-" + name)).write_text("ready\n")
    peer = root / ("ready-" + ("rt1" if name == "pystachy1" else "pystachy1"))
    deadline = time.monotonic() + 2
    while not peer.exists():
        if time.monotonic() >= deadline:
            print("rendezvous peer did not start", file=sys.stderr)
            sys.exit(9)
        time.sleep(0.005)
if os.getenv("HANG_NODE") == name:
    child = subprocess.Popen([sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"])
    (root / "child.pid").write_text(str(child.pid))
    time.sleep(60)
time.sleep(0.04)
if os.getenv("FAIL_NODE") == name:
    sys.exit(7)
if kind == "build":
    out.write_bytes(pathlib.Path(sys.argv[0]).read_bytes())
    out.chmod(0o700)
    if "--emit-ir" in argv:
        side = pathlib.Path(argv[argv.index("--emit-ir") + 1])
        if os.getenv("OMIT_NODE") != side.stem:
            side.write_text("program IR\n")
else:
    out.write_text("wrong\n" if os.getenv("MISMATCH_NODE") == name else
                   "runtime IR\n" if kind == "rt" else "program IR\n")
if os.getenv("MUTATE_NODE") == name:
    with (root / "runtime.py").open("a") as f:
        f.write("# changed\n")
'''


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "pystachy.py").write_text("#!" + sys.executable + "\n" + FAKE)
        (self.root / "runtime.py").write_text("# runtime\n")
        (self.root / "runtime.c").write_text("/* runtime */\n")
        self.output = self.root / "runs"

    def tearDown(self):
        self.temp.cleanup()

    def argv(self, variant="retained-ir", *extra):
        return ["--root", str(self.root), "--output", str(self.output), "--variant", variant,
                "--llvm", str(self.root / "fake-llvm"), *extra]

    def run_case(self, variant="retained-ir", extra=(), **env):
        output = io.StringIO()
        with patch.dict(os.environ, env), contextlib.redirect_stdout(output):
            code = pipeline.main(self.argv(variant, *extra))
        report = json.loads(Path(output.getvalue().strip()).read_text())
        events = [json.loads(line) for line in (self.root / "events.jsonl").read_text().splitlines()]
        return code, report, events

    def test_baseline_and_retention_preserve_independent_generations(self):
        for variant, ir_calls in (("baseline", 3), ("retained-ir", 1)):
            with self.subTest(variant=variant):
                (self.root / "events.jsonl").unlink(missing_ok=True)
                code, report, events = self.run_case(variant)
                self.assertEqual(code, 0)
                self.assertEqual(sum(e["kind"] == "build" for e in events), 2)
                self.assertEqual([e["producer"] for e in events if e["kind"] == "build"], ["pystachy.py", "pystachy1"])
                self.assertEqual(sum(e["kind"] == "ir" for e in events), ir_calls)
                self.assertEqual([e["producer"] for e in events if e["kind"] == "rt"],
                                 ["pystachy.py", "pystachy1", "pystachy2"])
                self.assertTrue(all(p["identical"] for p in report["fixed_points"].values()))
                self.assertTrue(all(n["status"] == "passed" for n in report["steps"]))
                self.assertGreater(report["cpu_seconds"], 0)

    def test_dag_overlaps_witnesses_and_respects_nested_worker_budget(self):
        code, report, events = self.run_case("optimized", ("--jobs", "3", "--build-jobs", "2", "--partitions", "2", "--stage1-opt", "1", "--runtime-c-cache", "--timing"), RENDEZVOUS="1")
        self.assertEqual(code, 0)
        steps = {n["name"]: n for n in report["steps"]}
        # Each command waited for the other's readiness before it could finish.
        # Parent wait4 timestamps alone cannot prove that child lifetimes overlap.
        self.assertTrue((self.root / "ready-pystachy1").exists())
        self.assertTrue((self.root / "ready-rt1").exists())
        for point in [n["started_seconds"] for n in steps.values()]:
            active = sum(n["slots"] for n in steps.values()
                         if n["started_seconds"] <= point < n["started_seconds"] + n["wall_seconds"])
            self.assertLessEqual(active, 3)
        builds = [e for e in events if e["kind"] == "build"]
        self.assertEqual([e["opt"] for e in builds], ["1", "2"])
        self.assertTrue(all(e["partitions"] == 2 and e["jobs"] == 2 for e in builds))
        self.assertTrue(all(e["partitions"] == 0 and e["jobs"] == 1 for e in events if e["kind"] != "build"))
        self.assertTrue(all(n["environment"]["PYSTACHY_RUNTIME_C_CACHE"] == "1" and
                            n["environment"]["PYSTACHY_TIMING"] == "1" for n in steps.values()))

    def test_rendezvous_rejects_sequential_scheduling(self):
        # setUp supplies a fresh root, so readiness from the positive control
        # cannot make a sequential execution appear concurrent.
        self.assertFalse(list(self.root.glob("ready-*")))
        code, report, _ = self.run_case("retained-ir", RENDEZVOUS="1")
        self.assertEqual(code, 1)
        self.assertEqual(report["steps"][0]["returncode"], 9)
        self.assertIn("rendezvous peer did not start", Path(report["steps"][0]["log"]).read_text())
        self.assertFalse((self.root / "ready-rt1").exists())

    def test_split_first_stage_keeps_three_independent_generations(self):
        # Model only the external build boundary; the fallible compiler still
        # emits every witness, including both independently built executables.
        script = self.root / "bench/compiler_host/self_pipeline.py"
        script.parent.mkdir(parents=True)
        script.write_text('''import json, pathlib, subprocess, sys
args = sys.argv[1:]
def value(flag):
    return args[args.index(flag) + 1]
root = pathlib.Path(value("--root"))
(root / "pipeline-arguments.json").write_text(json.dumps(args))
subprocess.run([sys.executable, str(root / "pystachy.py"), "build", "pystachy.py",
                "-o", value("--output"), "--emit-ir", value("--emit-ir")], check=True)
''')
        code, report, events = self.run_case("optimized", (
            "--jobs", "4", "--build-jobs", "4", "--stage1-opt", "0",
            "--stage1-split", "4", "--runtime-overlap", "--runtime-c-cache"))
        self.assertEqual(code, 0)
        builds = [e for e in events if e["kind"] == "build"]
        self.assertEqual([e["producer"] for e in builds], ["pystachy.py", "pystachy1"])
        self.assertEqual([e["opt"] for e in builds], ["0", "2"])
        self.assertTrue(all(e["partitions"] == 0 for e in builds))
        self.assertCountEqual([e["producer"] for e in events if e["kind"] == "rt"],
                              ["pystachy.py", "pystachy1", "pystachy2"])
        self.assertTrue(all(v["identical"] for v in report["fixed_points"].values()))
        self.assertEqual(sum(e["kind"] == "ir" for e in events), 1)
        arguments = json.loads((self.root / "pipeline-arguments.json").read_text())
        self.assertIn("--overlap", arguments)
        self.assertIn("--caller-witnesses", arguments)

    def test_split_policy_rejects_unaccounted_work_and_missing_witnesses(self):
        for extra in (("--stage1-split", "9", "--runtime-c-cache"),
                      ("--stage1-split", "4"),
                      ("--runtime-overlap",),
                      ("--stage1-split", "4", "--runtime-overlap", "--runtime-c-cache")):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    pipeline.main(self.argv("optimized", *extra))
                self.assertEqual(caught.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            pipeline.main(self.argv("baseline", "--stage1-split", "1", "--runtime-c-cache"))

    def test_failed_build_blocks_dependents_and_reports_diagnostics(self):
        code, report, events = self.run_case("optimized", ("--jobs", "2"), FAIL_NODE="pystachy1")
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertNotIn("pystachy2", [e["name"] for e in events])
        failed = next(n for n in report["steps"] if n["name"] == "build1")
        self.assertEqual(failed["returncode"], 7)
        self.assertTrue(Path(failed["log"]).exists())
        self.assertEqual(next(n for n in report["steps"] if n["name"] == "build2")["status"], "blocked")

    @unittest.skipUnless(sys.platform == "linux", "descendant state uses /proc")
    def test_failure_cancels_an_independent_running_job(self):
        code, report, _ = self.run_case("optimized", ("--jobs", "2"), FAIL_NODE="pystachy1", HANG_NODE="rt1")
        self.assertEqual(code, 1)
        self.assertLess(report["wall_seconds"], 3)
        self.assertLess(next(n for n in report["steps"] if n["name"] == "rt1")["returncode"], 0)
        self.assert_descendant_dead()

    def test_missing_sidecar_and_mismatched_ir_fail_closed(self):
        for env in ({"OMIT_NODE": "stage2"}, {"MISMATCH_NODE": "stage3"}, {"MISMATCH_NODE": "rt3"}):
            with self.subTest(env=env):
                code, report, _ = self.run_case(**env)
                self.assertEqual(code, 1)
                self.assertEqual(report["status"], "failed")
                self.assertIn("error", report)

    def test_source_change_invalidates_otherwise_matching_fixed_points(self):
        code, report, _ = self.run_case(MUTATE_NODE="pystachy2")
        self.assertEqual(code, 1)
        self.assertEqual(report["error"], "source files changed during bootstrap")

    def test_signal_after_popen_before_registration_cannot_orphan_child(self):
        popen = subprocess.Popen
        children = []

        def interrupted_launch(*args, **kwargs):
            child = popen(*args, **kwargs)
            if kwargs.get("start_new_session"):
                children.append(child.pid)
                # Inject precisely after OS launch, before run_nodes owns the PID.
                os.kill(os.getpid(), signal.SIGTERM)
            return child

        output = io.StringIO()
        with patch.object(pipeline.subprocess, "Popen", side_effect=interrupted_launch), contextlib.redirect_stdout(output):
            code = pipeline.main(self.argv())
        self.assertEqual(code, 143)
        self.assertEqual(len(children), 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(children[0], 0)
        report = json.loads(Path(output.getvalue().strip()).read_text())
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(report["steps"][0]["pid"], children[0])
        self.assertIn("returncode", report["steps"][0])

    @unittest.skipUnless(sys.platform == "linux", "descendant state uses /proc")
    def test_timeout_is_bounded_and_reaps_direct_child(self):
        began = time.monotonic()
        code, report, _ = self.run_case(extra=("--timeout", "0.15"), HANG_NODE="pystachy1")
        self.assertEqual(code, 1)
        self.assertLess(time.monotonic() - began, 3)
        node = report["steps"][0]
        self.assertTrue(node["timed_out"])
        with self.assertRaises(ProcessLookupError):
            os.kill(node["pid"], 0)
        self.assert_descendant_dead()

    def assert_descendant_dead(self):
        pid = int((self.root / "child.pid").read_text())
        # An orphaned zombie awaiting init's reap cannot execute; PID alone is insufficient.
        path = Path(f"/proc/{pid}/stat")
        for _ in range(100):
            if not path.exists() or path.read_text().split(")", 1)[1].split()[0] == "Z":
                return
            time.sleep(0.01)
        self.fail("owned descendant survived cleanup")

    @unittest.skipUnless(sys.platform == "linux", "descendant state uses /proc")
    def test_sigterm_preserves_partial_report_and_kills_descendants(self):
        env = dict(os.environ, HANG_NODE="pystachy1")
        proc = subprocess.Popen([sys.executable, str(SCRIPT), *self.argv()], env=env, stdout=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not (self.root / "child.pid").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.root / "child.pid").exists())
            proc.send_signal(signal.SIGTERM)
            output, _ = proc.communicate(timeout=3)
            self.assertEqual(proc.returncode, 143)
            report = json.loads(Path(output.strip()).read_text())
            self.assertEqual(report["status"], "interrupted")
            self.assertTrue(any(n["status"] == "blocked" for n in report["steps"]))
            self.assert_descendant_dead()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    unittest.main()
