"""Measurement/oracle regressions for the compiler parallelism controller.

No LLVM builds, network access or timing thresholds. The fake /proc cases model
the hosted sandbox's mismatched PID namespaces, which otherwise sample unrelated
processes and report plausible but incorrect memory figures.
"""
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("compiler_parallel_bench", ROOT / "bench/compiler_parallel/llvm_partitions.py")
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


def result(stdout: bytes = b"", stderr: bytes = b"", status: int = 0) -> dict:
    return {"stdout": stdout.decode("utf-8", "backslashreplace"),
            "stderr": stderr.decode("utf-8", "backslashreplace"),
            "stdout_sha256": bench.digest(stdout), "stderr_sha256": bench.digest(stderr),
            "exit_code": status, "timed_out": False, "command": ["fixture"]}


class ProcessAccounting(unittest.TestCase):
    def resolve(self, statuses, rows):
        def read(path, *args, **kwargs):
            if str(path) not in statuses:
                raise FileNotFoundError(path)
            return statuses[str(path)]
        with patch.object(Path, "read_text", autospec=True, side_effect=read), \
                patch.object(bench.os, "getpid", return_value=7), \
                patch.object(bench, "proc_snapshot", return_value=rows):
            return bench.proc_child_pid(8)

    def test_maps_own_child_across_pid_namespaces(self):
        statuses = {"/proc/self/status": "Pid:\t100\nNSpid:\t100 7\n",
                    "/proc/101/status": "Pid:\t101\nNSpid:\t101 8\n"}
        # The unrelated host PID 8 must not supply the measurements for child 8.
        self.assertEqual(self.resolve(statuses, [(8, 1, 900), (101, 100, 10)]), 101)

    def test_missing_mapping_never_falls_back_to_numeric_pid(self):
        statuses = {"/proc/self/status": "Pid:\t100\nNSpid:\t100 7\n",
                    "/proc/101/status": "Pid:\t101\n"}
        self.assertIsNone(self.resolve(statuses, [(8, 1, 900), (101, 100, 10)]))

    def test_ambiguous_mapping_is_unavailable(self):
        statuses = {"/proc/self/status": "Pid:\t100\nNSpid:\t100 7\n",
                    "/proc/101/status": "Pid:\t101\nNSpid:\t101 8\n",
                    "/proc/102/status": "Pid:\t102\nNSpid:\t102 8\n"}
        self.assertIsNone(self.resolve(statuses, [(101, 100, 10), (102, 100, 20)]))

    def test_same_namespace_does_not_need_parent_mapping(self):
        with patch.object(Path, "read_text", return_value="Pid:\t7\n"), \
                patch.object(bench.os, "getpid", return_value=7), \
                patch.object(bench, "proc_snapshot") as snapshot:
            self.assertEqual(bench.proc_child_pid(8), 8)
            snapshot.assert_not_called()

    def test_aggregate_includes_descendants_once_and_excludes_other_jobs(self):
        rows = [(10, 1, 100), (11, 10, 250), (12, 11, 75), (13, 999, 9000)]
        with patch.object(bench, "proc_snapshot", return_value=rows):
            self.assertEqual(bench.process_tree_rss(10), (425, 3))
            self.assertEqual(bench.process_tree_rss(99), (0, 0))

    def test_stat_handles_parentheses_in_process_name_and_page_units(self):
        fields = ["S", "4"] + ["0"] * 20
        fields[21] = "12"
        stat = "101 (worker ) name) " + " ".join(fields)
        with patch.object(Path, "iterdir", return_value=iter([Path("/proc/101"), Path("/proc/self")])), \
                patch.object(Path, "read_text", return_value=stat), \
                patch.object(bench.os, "sysconf", return_value=4096):
            self.assertEqual(bench.proc_snapshot(), [(101, 4, 48)])

    def test_unavailable_build_memory_cannot_become_a_measurement(self):
        measured = result(stderr=b"pystachy-timing\tdriver.total\t1\n")
        measured.update(proc_pid_resolved=False, sampled_process_tree_peak_rss_kib=None)
        with self.assertRaisesRegex(RuntimeError, "aggregate build RSS unavailable"):
            bench.build_stages(measured, {"jobs": 1, "partitions": 0}, "warm")


class ExactOracle(unittest.TestCase):
    def test_non_utf8_bytes_do_not_collapse_to_their_printable_escape(self):
        raw, escaped = result(b"\xff"), result(b"\\xff")
        self.assertEqual(raw["stdout"], escaped["stdout"])
        self.assertNotEqual(bench.witness(raw, False), bench.witness(escaped, False))

    def test_only_declared_json_timer_is_excluded(self):
        first = result(b"outputs [1, 2]\nchecksum 19\nseconds 0.001\n")
        second = result(b"outputs [1, 2]\nchecksum 19\nseconds 5.5\n")
        wrong = result(b"outputs [1, 2]\nchecksum 20\nseconds 0.001\n")
        self.assertEqual(bench.witness(first, True), bench.witness(second, True))
        self.assertNotEqual(bench.witness(first, True), bench.witness(wrong, True))

    def test_extra_missing_or_invalid_json_timer_is_rejected(self):
        for value in (b"checksum 19\n", b"seconds 1\nseconds 2\n",
                      b"warmup_seconds 1\nseconds 2\n", b"seconds nan\n", b"seconds -1\n"):
            with self.subTest(stdout=value), self.assertRaises(RuntimeError):
                bench.witness(result(value), True)

    def test_diagnostics_and_exit_status_remain_part_of_the_oracle(self):
        baseline = bench.witness(result(b"ok\n"), False)
        self.assertNotEqual(baseline, bench.witness(result(b"ok\n", b"warning\n"), False))
        self.assertNotEqual(baseline, bench.witness(result(b"ok\n", status=1), False))

    def test_timeout_and_failure_cannot_be_successful_output(self):
        for timed_out, status in ((True, 0), (False, 1)):
            row = result(b"correct\n", status=status)
            row["timed_out"] = timed_out
            with self.subTest(timed_out=timed_out), self.assertRaises(RuntimeError):
                bench.successful(row)


class ExecutedPathEvidence(unittest.TestCase):
    def test_old_compiler_ignoring_environment_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "driver.total"):
            bench.build_stages(result(), {"jobs": 1, "partitions": 0}, "warm")

    def test_lto_flag_without_lto_execution_is_rejected(self):
        row = result(stderr=b"pystachy-timing\tdriver.total\t1\n")
        with self.assertRaisesRegex(RuntimeError, "requested LLVM backend"):
            bench.build_stages(row, {"jobs": 4, "partitions": 4}, "warm")

    def test_cache_rebuild_does_not_count_as_a_warm_sample(self):
        row = result(stderr=b"pystachy-timing\truntime.frontend\t0.3\npystachy-timing\tdriver.total\t1\n")
        with self.assertRaisesRegex(RuntimeError, "warm build unexpectedly rebuilt"):
            bench.build_stages(row, {"jobs": 1, "partitions": 0}, "warm")


class NamegenProvenance(unittest.TestCase):
    def test_pin_is_recorded_but_earlier_shadowing_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            first.mkdir()
            second.mkdir()
            source = second / "namegen.py"
            source.write_text("# provenance fixture, no upstream implementation\n")
            workload = {"name": "namegen", "source": bench.NAMEGEN_PROBE, "imports": [first, second]}
            with patch.object(bench, "NAMEGEN_SHA256", bench.file_digest(source)):
                metadata = bench.source_provenance([workload])
                self.assertEqual(metadata[0]["url"], bench.NAMEGEN_URL)
                self.assertEqual(metadata[0]["path"], str(source))
                (first / "namegen.py").write_text("# a different module\n")
                with self.assertRaisesRegex(ValueError, "unchanged pinned"):
                    bench.source_provenance([workload])

    def test_package_shadowing_the_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "namegen").mkdir()
            (root / "namegen/__init__.py").write_text("")
            workload = {"name": "namegen", "source": bench.NAMEGEN_PROBE, "imports": [root]}
            with self.assertRaisesRegex(ValueError, "package shadows"):
                bench.source_provenance([workload])


class GeneratedInputIdentity(unittest.TestCase):
    def test_warmup_source_is_part_of_input_identity_without_a_tiny_workload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("pystachy.py", "runtime.py", "runtime.c"):
                (root / name).write_text("")
            warmup = root / "tiny.py"
            warmup.write_text('print("warmup")\n')
            with patch.object(bench, "ROOT", root):
                before = bench.identify_sources([], (warmup,))
                self.assertEqual(before["files"][str(warmup)], bench.file_digest(warmup))
                warmup.write_text('print("changed")\n')
                after = bench.identify_sources([], (warmup,))
            self.assertNotEqual(before["sha256"], after["sha256"])


class WorkloadEnvironment(unittest.TestCase):
    def test_json_repair_oracle_imports_the_bundled_package_and_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            workload = bench.choose_workloads(["json-repair"], Path(directory))[0]
            env = bench.runtime_environment(dict(os.environ), workload)
            probe = subprocess.run([sys.executable, str(workload["source"]), "0"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn("outputs ", probe.stdout)
            self.assertIn("checksum 0\n", probe.stdout)
            imported = subprocess.run([sys.executable, "-c", "import json_repair; print(json_repair.__file__)"],
                                      cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertEqual(Path(imported.stdout.strip()), ROOT / "ports/json_repair/__init__.py")
            self.assertEqual(env["PYSTACHY_PATH"], env["PYTHONPATH"])

    def test_resolving_an_interpreter_preserves_its_virtualenv_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "venv/bin/python"
            executable.parent.mkdir(parents=True)
            executable.symlink_to(sys.executable)
            command = bench.resolve_command(shlex.quote(str(executable)) + " -m pystachy")
            self.assertEqual(command, [str(executable), "-m", "pystachy"])
            # Content identity can still use the target's bytes.
            self.assertEqual(bench.command_identity([str(executable)]),
                             bench.command_identity([str(executable.resolve())]))


if __name__ == "__main__":
    unittest.main()
