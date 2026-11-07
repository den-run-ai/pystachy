"""The optional libuv check's independent TCP oracle fails closed without libuv."""

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "examples" / "uvio" / "check.py"
spec = importlib.util.spec_from_file_location("check_uvio", SOURCE)
uvio_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uvio_check)


class WrongPeer(uvio_check.Peer):
    def serve(self, connection):
        with connection:
            connection.settimeout(3)
            while connection.recv(4096):
                pass
            connection.sendall(b"wrong response")


class CheckerTests(unittest.TestCase):
    def test_real_stdlib_oracle_and_held_request_protocol(self):
        with uvio_check.Peer() as peer:
            uvio_check.socket_oracle(peer)
            with socket.create_connection(("127.0.0.1", peer.port), timeout=3) as held:
                held.sendall(b"hold")
                held.shutdown(socket.SHUT_WR)
                held.settimeout(0.05)
                with self.assertRaises(TimeoutError):
                    held.recv(1)
                with socket.create_connection(("127.0.0.1", peer.port), timeout=3) as released:
                    released.sendall(b"release")
                    released.shutdown(socket.SHUT_WR)
                    with released.makefile("rb") as response:
                        self.assertEqual(response.read(), b"released")
                held.settimeout(3)
                with held.makefile("rb") as response:
                    self.assertEqual(response.read(), b"slow")

    def test_oracle_rejects_corrupt_peer_output(self):
        with WrongPeer() as peer:
            with self.assertRaisesRegex(AssertionError, "oracle disagrees"):
                uvio_check.socket_oracle(peer)

    def test_peer_worker_failure_reaches_caller(self):
        with self.assertRaisesRegex(AssertionError, "unknown peer command"):
            with uvio_check.Peer() as peer:
                with socket.create_connection(("127.0.0.1", peer.port), timeout=3) as connection:
                    connection.sendall(b"invalid")
                    connection.shutdown(socket.SHUT_WR)
                    self.assertEqual(connection.recv(1), b"")

    def test_runner_rejects_nonzero_status_and_stderr(self):
        for code in ["raise SystemExit(2)", "import sys; sys.stderr.write('diagnostic')"]:
            with self.subTest(code=code), self.assertRaises(RuntimeError):
                uvio_check.run([sys.executable, "-c", code], os.environ.copy())
        self.assertEqual(uvio_check.run([sys.executable, "-c", "print('ok')"], os.environ.copy()), b"ok\n")

    def test_timeout_terminates_compiler_descendants(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "escaped-child"
            child = "import pathlib,sys,time; time.sleep(1); pathlib.Path(sys.argv[1]).touch()"
            parent = ("import subprocess,sys,time; "
                      f"subprocess.Popen([sys.executable, '-c', {child!r}, sys.argv[1]]); time.sleep(30)")
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                uvio_check.run([sys.executable, "-c", parent, str(marker)], os.environ.copy(), timeout=0.2)
            # Inherited capture pipes keep communicate() waiting if only the parent dies.
            self.assertFalse(marker.exists())

    def test_report_replaces_stale_pass_before_work_and_records_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps({"result": "pass", "runs": {"old": {}}}))

            def fail(args, report):
                self.assertEqual(json.loads(path.read_text()), {"result": "running", "runs": {}})
                raise RuntimeError("changed source")

            with mock.patch.object(uvio_check, "check", side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(uvio_check.main(["--json", str(path)]), 1)
            self.assertEqual(json.loads(path.read_text()), {"result": "fail", "runs": {}, "error": "changed source"})
            with mock.patch.object(uvio_check, "check"):
                self.assertEqual(uvio_check.main(["--json", str(path)]), 0)
            self.assertEqual(json.loads(path.read_text()), {"result": "pass", "runs": {}})

    def test_source_guard_rejects_consumed_edits_and_excludes_readme(self):
        before = uvio_check.source_hashes()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in before:
                (directory / name).write_bytes((uvio_check.HERE / name).read_bytes())
            with mock.patch.object(uvio_check, "HERE", directory):
                (directory / "README.md").write_text("review notes may change")
                report = {}
                uvio_check.verify_sources(before, report)
                self.assertEqual(report["sources_after"], before)
                with (directory / "bridge.c").open("a") as source:
                    source.write("\n/* changed */\n")
                with self.assertRaisesRegex(RuntimeError, "consumed sources changed"):
                    uvio_check.verify_sources(before, report)
                self.assertNotEqual(report["sources_after"], before)


if __name__ == "__main__":
    unittest.main()
