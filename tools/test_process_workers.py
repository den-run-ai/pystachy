"""Resource admission, bounded result handling and immutable artifact controls."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import application_workers as application
import process_workers as workers
import worker_artifacts as artifacts
from test_compiler_parallel_workers import BLOCK, living


TOOLS = Path(__file__).resolve().parent


class ResourceTests(unittest.TestCase):
    def job(self, key, resources=None, source="print('done')"):
        return workers.Job(key, [sys.executable, "-c", source], resources)

    def test_cpu_memory_and_input_reservations_each_bound_live_jobs(self):
        cases = (
            workers.Resources(cpu=2, memory_bytes=1, input_bytes=1),
            workers.Resources(cpu=1, memory_bytes=6, input_bytes=1),
            workers.Resources(cpu=1, memory_bytes=1, input_bytes=6),
        )
        budget = workers.Budget(cpu=2, memory_bytes=8, input_bytes=8)
        for request in cases:
            with self.subTest(request=request.as_dict()), workers.Commands(owns_group=False) as scope:
                jobs = [self.job(index, request) for index in range(3)]
                results = list(scope.run(jobs, dict(os.environ), timeout=5, jobs=3, budget=budget))
                self.assertEqual([row["key"] for row in results], [0, 1, 2])
                self.assertTrue(all(row["exit_code"] == 0 for row in results))
                self.assertEqual(scope.peak_reserved, request.as_dict())
                for previous, current in zip(results, results[1:]):
                    self.assertLessEqual(previous["finished_monotonic_s"], current["started_monotonic_s"])

    def test_oversized_or_unqueueable_jobs_are_rejected_before_spawn(self):
        requests = (workers.Resources(cpu=3), workers.Resources(memory_bytes=9),
                    workers.Resources(input_bytes=9), workers.Resources(input_bytes=5))
        budget = workers.Budget(cpu=2, memory_bytes=8, input_bytes=8, queued_bytes=4)
        for request in requests:
            with self.subTest(request=request.as_dict()), workers.Commands(owns_group=False) as scope, \
                    patch.object(scope, "start") as start, self.assertRaises(ValueError):
                list(scope.run([self.job("oversized", request)], dict(os.environ), timeout=5, jobs=2, budget=budget))
            start.assert_not_called()

    def test_queue_consumption_is_lazy_with_one_waiting_descriptor(self):
        consumed = []

        def jobs():
            for index in range(100):
                consumed.append(index)
                yield self.job(index, workers.Resources(input_bytes=4))

        with workers.Commands(owns_group=False) as scope:
            results = scope.run(jobs(), dict(os.environ), timeout=5, jobs=8,
                                budget=workers.Budget(cpu=1, memory_bytes=0, input_bytes=4, queued_bytes=4))
            self.assertEqual(next(results)["key"], 0)
            self.assertEqual(consumed, [0, 1])
            results.close()
        self.assertEqual([row["key"] for row in scope.results], [0])

    def test_captures_are_bounded_but_normal_output_hashes_remain_complete(self):
        output, error = b"x" * 5000, b"e" * 2000
        job = self.job("output", source="import os; os.write(1, b'x'*5000); os.write(2, b'e'*2000)")
        with workers.Commands(owns_group=False, capture_bytes=37) as scope:
            result = next(scope.run([job], dict(os.environ), timeout=5))
        self.assertEqual(result["stdout"], "x" * 37)
        self.assertEqual(result["stderr"], "e" * 37)
        for name, data in (("stdout", output), ("stderr", error)):
            self.assertEqual(result[name + "_bytes"], len(data))
            self.assertEqual(result[name + "_hashed_bytes"], len(data))
            self.assertEqual(result[name + "_sha256"], hashlib.sha256(data).hexdigest())
            self.assertIsNone(result[name + "_prefix_sha256"])
            self.assertTrue(result[name + "_truncated"])

    def test_sparse_oversized_output_cannot_force_unbounded_cleanup_reads(self):
        original = tempfile.TemporaryFile
        streams = []

        class TrackedStream:
            def __init__(self):
                self.stream, self.bytes_read = original(), 0
                streams.append(self)

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def read(self, count=-1):
                value = self.stream.read(count)
                self.bytes_read += len(value)
                return value

        job = self.job("sparse", source="import os; os.ftruncate(1, 8*1024*1024)")
        scope = workers.Commands(owns_group=False, capture_bytes=128, output_limit_bytes=1024)
        with patch.object(workers.tempfile, "TemporaryFile", side_effect=TrackedStream), \
                self.assertRaisesRegex(RuntimeError, "output byte limit"), scope:
            list(scope.run([job], dict(os.environ), timeout=5))
        self.assertLessEqual(sum(stream.bytes_read for stream in streams), 1024)
        self.assertEqual(len(scope.results), 1)
        result = scope.results[0]
        self.assertTrue(result["output_limit_exceeded"])
        self.assertEqual(result["stdout_bytes"], 8 * 1024 * 1024)
        self.assertEqual(result["stdout_hashed_bytes"], 1024)
        self.assertIsNone(result["stdout_sha256"])
        self.assertEqual(result["stdout_prefix_sha256"], hashlib.sha256(b"\0" * 1024).hexdigest())
        self.assertEqual(len(result["stdout"]), 128)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = artifacts.ArtifactCache(self.root / "cache")
        self.source = self.root / "input.o"
        self.source.write_bytes(b"verified object bytes")
        self.key = artifacts.key_for({"job": "first"})

    def test_mutating_source_cannot_corrupt_previously_published_object(self):
        with self.cache.locked(self.key):
            record = self.cache.publish(self.key, self.source)
        original = self.source.read_bytes()
        second = artifacts.key_for({"job": "second"})
        copy = artifacts.shutil.copyfileobj

        def concurrent_mutation(source, destination):
            self.source.write_bytes(b"changed while publishing")
            copy(source, destination)

        with self.cache.locked(second), patch.object(artifacts.shutil, "copyfileobj", side_effect=concurrent_mutation), \
                self.assertRaisesRegex(RuntimeError, "changed during"):
            self.cache.publish(second, self.source)
        hit = self.cache.lookup(self.key)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0].read_bytes(), original)
        self.assertEqual(hit[1], record)
        self.assertIsNone(self.cache.lookup(second))
        self.assertEqual(list((self.cache.root / "objects").glob("pending-*")), [])

    def test_pointer_failure_keeps_old_entry_and_corruption_is_a_miss(self):
        with self.cache.locked(self.key):
            self.cache.publish(self.key, self.source)
        previous = self.cache.lookup(self.key)
        self.source.write_bytes(b"new valid output")
        with self.cache.locked(self.key), patch.object(artifacts, "atomic_json", side_effect=OSError("publish failed")), \
                self.assertRaises(OSError):
            self.cache.publish(self.key, self.source)
        self.assertEqual(self.cache.lookup(self.key), previous)
        previous[0].write_bytes(b"corrupt")
        self.assertIsNone(self.cache.lookup(self.key))

    def test_contended_lock_times_out_without_releasing_the_owner(self):
        with self.cache.locked(self.key):
            with self.assertRaisesRegex(TimeoutError, "acquisition timed out"), self.cache.locked(self.key, timeout=0):
                self.fail("contended cache lock was acquired")
            self.cache.publish(self.key, self.source)
        self.assertIsNotNone(self.cache.lookup(self.key))

    def test_lookup_byte_bound_rejects_sparse_objects_before_hashing(self):
        with self.cache.locked(self.key):
            record = self.cache.publish(self.key, self.source)
        hit = self.cache.lookup(self.key, max_bytes=len(self.source.read_bytes()))
        self.assertIsNotNone(hit)
        with hit[0].open("wb") as stream:
            stream.truncate(8 * 1024 * 1024)
        record["bytes"] = 8 * 1024 * 1024
        pointer = self.cache.root / "entries" / (self.key + ".json")
        pointer.write_text(json.dumps(record))
        with patch.object(artifacts, "sha256", side_effect=AssertionError("oversized artifact was read")):
            self.assertIsNone(self.cache.lookup(self.key, max_bytes=1024))

    def test_processes_deduplicate_a_concurrent_miss(self):
        script = self.root / "consumer.py"
        script.write_text('''import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
from worker_artifacts import ArtifactCache
cache, key, source, counter = ArtifactCache(sys.argv[2]), sys.argv[3], pathlib.Path(sys.argv[4]), pathlib.Path(sys.argv[5])
with cache.locked(key, timeout=5):
    if cache.lookup(key) is None:
        with counter.open("a") as stream:
            stream.write("built\\n")
        time.sleep(.03)
        cache.publish(key, source)
        print("built")
    else:
        print("hit")
''')
        counter = self.root / "executions.txt"
        command = [sys.executable, "-I", str(script), str(TOOLS), str(self.cache.root), self.key,
                   str(self.source), str(counter)]
        processes = []
        try:
            processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                         for _ in range(3)]
            outputs = []
            for process in processes:
                output, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, error)
                outputs.append(output.strip())
            self.assertEqual(sorted(outputs), ["built", "hit", "hit"])
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.wait()
        self.assertEqual(counter.read_text().splitlines(), ["built"])
        self.assertEqual(self.cache.lookup(self.key)[0].read_bytes(), self.source.read_bytes())


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pystachy-application-workers-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest, self.report = self.root / "jobs.json", self.root / "report.json"

    def job(self, key, source, *arguments, **options):
        return {"key": key, "argv": [sys.executable, "-c", source, *map(str, arguments)],
                "memory_bytes": 1024 * 1024, **options}

    def write(self, jobs):
        self.manifest.write_text(json.dumps({"version": 1, "jobs": jobs}))

    def invoke(self, report=None):
        command = [sys.executable, str(TOOLS / "application_workers.py"), str(self.manifest),
                   "--report", str(report or self.report), "--jobs", "2", "--cpus", "2", "--memory-mib", "64",
                   "--input-mib", "1", "--queued-input-mib", "1", "--timeout", "3"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)

        def cleanup():
            try:
                os.killpg(process.pid, workers.signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

        # Keep fallback cleanup after assertions; doing it on normal return
        # would hide an application controller that left grandchildren alive.
        self.addCleanup(cleanup)
        try:
            output, error = process.communicate(timeout=10)
        except BaseException:
            cleanup()
            raise
        return subprocess.CompletedProcess(command, process.returncode, output, error)

    def test_stdin_nested_thread_caps_and_submission_order(self):
        (self.root / "input.txt").write_text("batch data\n")
        self.write([
            self.job("first", "import os,sys,time; time.sleep(.03); print(sys.stdin.read().strip(), os.environ['OMP_NUM_THREADS'])",
                     stdin="input.txt", input_bytes=11, env={"OMP_NUM_THREADS": "99"}),
            self.job("second", "print('second')"),
        ])
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertTrue(report["complete"])
        self.assertEqual([row["key"] for row in report["results"]], ["first", "second"])
        self.assertEqual([row["stdout"] for row in report["results"]], ["batch data 1\n", "second\n"])
        self.assertLessEqual(report["peak_reserved"]["cpu"], 2)
        self.assertEqual(report["peak_reserved"]["input_bytes"], 11)

    def test_stdin_reservation_failure_does_not_spawn_work(self):
        (self.root / "input.txt").write_text("batch data\n")
        self.write([self.job("too-large", "print('must not run')", stdin="input.txt", input_bytes=1)])
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["results"], [])
        self.assertIn("stdin artifact exceeds", report["error"])

    def test_failure_cancels_children_and_never_starts_queued_job(self):
        marker, queued = self.root / "blocking.pid", self.root / "queued"
        failure = "import pathlib,sys,time; p=pathlib.Path(sys.argv[1]);\nwhile not p.exists(): time.sleep(.005)\nsys.exit(7)"
        self.write([
            self.job("blocking", BLOCK, marker),
            self.job("failure", failure, str(marker) + ".ready"),
            self.job("queued", "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", queued),
        ])
        result = self.invoke()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report.read_text())
        self.assertFalse(report["complete"])
        self.assertEqual([row["key"] for row in report["results"]], ["blocking", "failure"])
        self.assertTrue(report["results"][0]["cancelled"])
        self.assertEqual(report["results"][1]["exit_code"], 7)
        self.assertFalse(queued.exists())
        for path in (marker, Path(str(marker) + ".child")):
            self.assertFalse(living(int(path.read_text())))

    def test_bad_path_and_environment_types_are_validation_errors(self):
        for values in ({"stdin": 1}, {"stdin": []}, {"cwd": 1}, {"env": {"": "invalid"}}):
            self.write([self.job("invalid", "print('unused')", **values)])
            with self.subTest(values=values), self.assertRaises(ValueError):
                list(application.read_jobs(self.manifest))

    def test_path_lookup_cannot_hide_report_executable_collision(self):
        directory = self.root / "bin"
        directory.mkdir()
        executable = directory / "worker"
        original = b"#!/bin/sh\nexit 0\n"
        executable.write_bytes(original)
        executable.chmod(0o755)
        self.manifest.write_text(json.dumps({"version": 1, "jobs": [{
            "key": "worker", "argv": ["worker"], "env": {"PATH": str(directory)}}]}))
        with self.assertRaisesRegex(ValueError, "absolute executable"):
            list(application.read_jobs(self.manifest))
        result = self.invoke(report=executable)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absolute executable", result.stderr)
        self.assertEqual(executable.read_bytes(), original)

    def test_reports_cannot_replace_the_manifest_or_stdin_artifact(self):
        source = self.root / "input.txt"
        source.write_text("source must survive\n")
        self.write([self.job("valid", "pass", stdin="input.txt", input_bytes=20)])
        for target in (self.manifest, source):
            previous = target.read_bytes()
            with self.subTest(target=target.name):
                result = self.invoke(report=target)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(target.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
