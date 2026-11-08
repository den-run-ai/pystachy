"""Source-transfer workload and report checks run without an installed libuv."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import types
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parents[1] / "examples" / "uvio"


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load("uvio_check_dogfood", "check.py")
with mock.patch.dict(sys.modules, {"check": checker, "uvio": types.SimpleNamespace(Loop=object)}):
    dogfood = load("uvio_dogfood", "dogfood.py")
    consumer = load("uvio_source_exchange", "source_exchange.py")
sockets = load("uvio_socket_exchange", "socket_exchange.py")


class Completion:
    def __init__(self, request, data, status=0):
        self.request_id = request
        self.data = data
        self.status = status

    def error_name(self):
        return "ETIMEDOUT"


class ReorderedLoop:
    """Expose empty turns and reverse completions to exercise real API contracts."""

    def __init__(self):
        self.pending = []
        self.submitted = 0
        self.max_pending = 0
        self.turns = 0

    def submit(self, address, port, data, timeout_ms):
        assert address == "127.0.0.1" and port == 12345 and timeout_ms == 5000
        assert data.startswith(b"E")
        self.submitted += 1
        self.pending.append(Completion(self.submitted, data[1:]))
        self.max_pending = max(self.max_pending, len(self.pending))
        return self.submitted

    def run_once(self):
        self.turns += 1
        if self.turns % 2:
            return []
        result = list(reversed(self.pending))
        self.pending.clear()
        return result


class WrongPeer(checker.Peer):
    def serve(self, connection):
        with connection:
            connection.settimeout(3)
            while connection.recv(4096):
                pass
            connection.sendall(b"wrong")


class SourceTests(unittest.TestCase):
    def test_chunking_preserves_binary_and_empty_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.py"
            for data in (b"", bytes(range(256)) * 5):
                source.write_bytes(data)
                chunks = consumer.source_chunks(str(source), 123)
                self.assertEqual(b"".join(chunks), data)
                self.assertTrue(chunks)
                self.assertTrue(all(len(chunk) <= 123 for chunk in chunks))
            for invalid in (0, -1, 65536):
                with self.assertRaises(ValueError):
                    consumer.source_chunks(str(source), invalid)
            source.write_bytes(b"x" * 1048577)
            with self.assertRaisesRegex(ValueError, "1 MiB"):
                consumer.source_chunks(str(source), 123)

    def test_bounded_refill_matches_reordered_binary_completions(self):
        loop = ReorderedLoop()
        chunks = [b"a\x00b", bytes(range(256)), b""]
        count, requests, steps = consumer.exchange(loop, 12345, chunks, 3, 2)
        self.assertEqual((count, requests), (259 * 3, 9))
        self.assertEqual(loop.max_pending, 2)
        self.assertGreater(steps, 1)
        self.assertFalse(loop.pending)

    def test_consumer_rejects_corruption_unknown_duplicate_and_failed_completion(self):
        for events, message in [
            ([Completion(1, b"corrupt")], "source bytes changed"),
            ([Completion(42, b"expected")], "unknown or duplicate"),
            ([Completion(1, b"expected"), Completion(1, b"expected")], "unknown or duplicate"),
            ([Completion(1, b"expected", -1)], "ETIMEDOUT"),
        ]:
            with self.subTest(message=message):
                loop = ReorderedLoop()
                loop.run_once = lambda events=events: events
                with self.assertRaisesRegex(AssertionError, message):
                    consumer.exchange(loop, 12345, [b"expected"], 1, 1)

    def test_consumer_rejects_reused_live_id_and_invalid_bounds(self):
        loop = ReorderedLoop()
        loop.submit = lambda *args: 1
        with self.assertRaisesRegex(AssertionError, "ID reused"):
            consumer.exchange(loop, 12345, [b"x"], 2, 2)
        for chunks, rounds, concurrency in [([], 1, 1), ([b"x"], 0, 1), ([b"x"], 1, 0), ([b"x"], 1, 65)]:
            with self.assertRaises(ValueError):
                consumer.exchange(loop, 12345, chunks, rounds, concurrency)


class SocketTests(unittest.TestCase):
    def test_independent_socket_baseline_binary_fragmented_and_empty(self):
        chunks = [b"", b"zero\x00byte", bytes(range(256)) * 32]
        with checker.Peer() as peer:
            count, requests, steps = sockets.exchange(peer.port, chunks, 2, 3)
        self.assertEqual((count, requests), (sum(map(len, chunks)) * 2, 6))
        self.assertGreater(steps, 0)

    def test_socket_failure_closes_every_owned_socket(self):
        owned = []
        real_socket = socket.socket

        def tracked_socket(*args, **kwargs):
            connection = real_socket(*args, **kwargs)
            owned.append(connection)
            return connection

        with WrongPeer() as peer:
            # The listening socket already exists. Include accepted sockets in the
            # recording too; all of them must close when Peer joins its workers.
            with mock.patch.object(sockets.socket, "socket", side_effect=tracked_socket):
                with self.assertRaisesRegex(AssertionError, "source bytes changed"):
                    sockets.exchange(peer.port, [b"expected"], 1, 1)
        self.assertTrue(owned)
        self.assertTrue(all(connection.fileno() == -1 for connection in owned))


class ReportTests(unittest.TestCase):
    def test_commands_preserve_module_and_code_arguments_matching_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("pystachy", "pystachy.py"):
                (directory / name).write_text("fixture")
            with mock.patch.object(dogfood, "ROOT", directory):
                for option in ("-m", "-c"):
                    self.assertEqual(dogfood.command_words(f"python {option} pystachy"),
                                     ["python", option, "pystachy"])
                self.assertEqual(dogfood.command_words("./pystachy"), [str(directory / "pystachy")])
                self.assertEqual(dogfood.command_words("python pystachy.py"),
                                 ["python", str(directory / "pystachy.py")])

    def test_compiler_hashes_cover_python_packages_and_c_runtime_dependencies(self):
        names = ("pystachy.py", "runtime.py", "runtime.c", "runtime.h", "src/__init__.py",
                 "src/other/nested.py", "lib/helper.py", "ryu/d2s.c", "ryu/detail/helper.h",
                 "mpz/mpz.c", "mpz/detail/helper.h")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in names:
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            with mock.patch.object(dogfood, "ROOT", directory):
                before = dogfood.compiler_hashes()
                self.assertEqual(set(before), set(names))
                (directory / "ryu/detail/helper.h").write_text("changed header")
                self.assertNotEqual(before["ryu/detail/helper.h"], dogfood.compiler_hashes()["ryu/detail/helper.h"])

    def test_invalid_or_oversized_input_is_rejected_before_hashing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "large.py"
            source.write_bytes(b"x" * 1048577)
            for path in (directory, directory / "missing.py", source):
                args = types.SimpleNamespace(samples=1, rounds=1, chunks=[4096], concurrency=[1], source=path)
                with self.subTest(path=path), mock.patch.object(dogfood, "source_hashes") as hashes:
                    with self.assertRaises(ValueError):
                        dogfood._benchmark(args, {})
                    hashes.assert_not_called()

    def test_controller_rejects_wrong_version_or_implementation_before_work(self):
        required = (dogfood.ROOT / ".python-version").read_text().strip()
        for implementation, version in [("CPython", "0.0.0"), ("PyPy", required)]:
            with self.subTest(implementation=implementation), \
                 mock.patch.object(dogfood.platform, "python_implementation", return_value=implementation), \
                 mock.patch.object(dogfood.platform, "python_version", return_value=version), \
                 mock.patch.object(dogfood, "_benchmark") as work:
                with self.assertRaisesRegex(RuntimeError, "controller requires CPython"):
                    dogfood.benchmark(types.SimpleNamespace(cpu=None), {})
                work.assert_not_called()

    def test_affinity_is_restored_after_success_or_failure(self):
        required = (dogfood.ROOT / ".python-version").read_text().strip()
        for failure in (None, RuntimeError("work failed")):
            with self.subTest(failure=failure), \
                 mock.patch.object(dogfood.platform, "python_implementation", return_value="CPython"), \
                 mock.patch.object(dogfood.platform, "python_version", return_value=required), \
                 mock.patch.object(dogfood.os, "sched_getaffinity", return_value={2, 7}, create=True), \
                 mock.patch.object(dogfood.os, "sched_setaffinity", create=True) as set_affinity, \
                 mock.patch.object(dogfood, "_benchmark", side_effect=failure):
                if failure:
                    with self.assertRaisesRegex(RuntimeError, "work failed"):
                        dogfood.benchmark(types.SimpleNamespace(cpu=2), {})
                else:
                    dogfood.benchmark(types.SimpleNamespace(cpu=2), {})
                self.assertEqual(set_affinity.call_args_list, [mock.call(0, {2}), mock.call(0, {2, 7})])

    def test_profile_rejects_bad_counts_and_child_environment_uses_private_cache(self):
        environments = []

        def run(command, env, **kwargs):
            environments.append(env.copy())
            if "-c" in command:
                return b"fixture interpreter\n"
            if "--version" in command:
                return b"fixture compiler\n"
            if "cProfile" in command:
                return b"1 6 1 1\n"  # The input contains seven bytes.
            if str(HERE / "bridge.c") in command:
                Path(command[-1]).write_bytes(b"fixture bridge")
                return b""
            return b"1 7 1 1\n"

        required = (dogfood.ROOT / ".python-version").read_text().strip()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "source.py"
            source.write_bytes(b"payload")
            (directory / "lib").mkdir()
            (directory / "lib" / "libuv.so").write_bytes(b"fixture libuv")
            report_path = directory / "report.json"
            inherited = {"PYTHONINSPECT": "1", "PYTHONSTARTUP": "ignored-file",
                         "PYSTACHY_CACHE": str(directory / "shared-cache"), "PYSTACHY_PROGRAM_CACHE": "1"}
            with mock.patch.dict(os.environ, inherited), \
                 mock.patch.object(dogfood.platform, "python_implementation", return_value="CPython"), \
                 mock.patch.object(dogfood.platform, "python_version", return_value=required), \
                 mock.patch.object(dogfood, "run", side_effect=run), \
                 mock.patch.object(dogfood.subprocess, "check_output", return_value="fixture-head\n"), \
                 mock.patch.object(dogfood.ctypes, "CDLL") as library, \
                 mock.patch.object(dogfood, "Peer") as peer, \
                 mock.patch.object(dogfood, "profile_summary") as summary, \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                library.return_value.uvio_version.return_value = b"fixture libuv"
                peer.return_value.__enter__.return_value.port = 12345
                self.assertEqual(dogfood.main([
                    "--cpython-only", "--source", str(source), "--libuv-prefix", str(directory),
                    "--samples", "1", "--rounds", "1", "--chunks", "4096", "--concurrency", "1",
                    "--profile", str(directory / "profiles"), "--json", str(report_path),
                ]), 1)
                summary.assert_not_called()
            report = json.loads(report_path.read_text())
            self.assertEqual(report["result"], "fail")
            self.assertIn("expected source transfers", report["error"])
            self.assertIn("-O2", report["cc_flags"])
            self.assertIn("-luv", report["cc_link_flags"])
            for env in environments:
                self.assertNotIn("PYTHONINSPECT", env)
                self.assertNotIn("PYTHONSTARTUP", env)
                for name in ("PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE", "PYTHONUTF8"):
                    self.assertEqual(env[name], "1")
                self.assertEqual(env["PYTHONHASHSEED"], "0")
                self.assertEqual(env["PYSTACHY_PROGRAM_CACHE"], "0")
            cache = Path(report["environment"]["PYSTACHY_CACHE"])
            self.assertNotEqual(str(cache), inherited["PYSTACHY_CACHE"])
            self.assertFalse(cache.parent.exists())

    def test_report_accepts_exact_transfer_counts_including_empty_source(self):
        self.assertEqual(dogfood.parse_sample(b"0.01 513 3 5\n", 513, 256, 1)["exchanges"], 3)
        self.assertEqual(dogfood.parse_sample(b"0.01 0 3 5\n", 0, 256, 3)["exchanges"], 3)

    def test_report_rejects_invalid_times_counts_and_extraneous_output(self):
        for output in (b"nan 10 1 1", b"inf 10 1 1", b"0 10 1 1", b"-1 10 1 1",
                       b"1 9 1 1", b"1 10 2 1", b"1 10 1 0", b"log\n1 10 1 1"):
            with self.subTest(output=output), self.assertRaises(AssertionError):
                dogfood.parse_sample(output, 10, 256, 1)

    def test_report_replaces_stale_pass_before_work_and_records_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps({"result": "pass", "results": ["stale"]}))

            def fail(args, report):
                self.assertEqual(json.loads(path.read_text()), {"result": "running"})
                raise RuntimeError("changed source")

            with mock.patch.object(dogfood, "benchmark", side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(dogfood.main(["--json", str(path)]), 1)
            self.assertEqual(json.loads(path.read_text()), {"result": "fail", "error": "changed source"})
            with mock.patch.object(dogfood, "benchmark"):
                self.assertEqual(dogfood.main(["--json", str(path)]), 0)
            self.assertEqual(json.loads(path.read_text()), {"result": "pass"})


if __name__ == "__main__":
    unittest.main()
