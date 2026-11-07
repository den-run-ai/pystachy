"""Detached protocol integrity, leases, cleanup and retry-policy regressions."""
from __future__ import annotations

import base64
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import worker_transport as transport
from test_compiler_parallel_workers import BLOCK, living


SCRIPT = Path(transport.__file__).resolve()


def spec(**changes):
    value = {"version": 1, "commands": [["@tool:copy", "input.txt", "output.txt"]],
             "inputs": {"input.txt": False}, "outputs": ["output.txt"],
             "cpu": 1, "memory_bytes": 1024 * 1024, "timeout_s": 5, "lease_s": 1,
             "idempotent": True, "cacheable": True}
    value.update(changes)
    return value


class ProtocolTests(unittest.TestCase):
    def test_artifact_integrity_modes_and_relative_names_are_checked(self):
        valid = {"sha256": hashlib.sha256(b"x").hexdigest(), "bytes": 1,
                 "executable": False, "data": base64.b64encode(b"x").decode()}
        self.assertEqual(transport.unpack_file(valid), b"x")
        for change in ({"bytes": True}, {"bytes": transport.FILE_LIMIT + 1}, {"sha256": "0" * 64},
                       {"data": "!!!"}, {"executable": 0}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                transport.unpack_file(dict(valid, **change))
        for name in ("../escape", "/absolute", "sub/../escape", "sub//file", ".", "bad\nname"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                transport.validate_spec(spec(outputs=[name]))
        with self.assertRaises(ValueError):
            transport.validate_spec(spec(idempotent=False, cacheable=True))

    def test_expired_lease_cannot_be_revived_by_a_queued_renewal(self):
        read_fd, write_fd = os.pipe()
        try:
            with patch.object(transport.time, "monotonic", return_value=10):
                lease = transport.Lease(read_fd, "nonce", .5)
            os.write(write_fd, b'{"renew":"nonce"}\n')
            with patch.object(transport.time, "monotonic", return_value=10.6), \
                    self.assertRaisesRegex(TimeoutError, "lease expired"):
                lease.tick()
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_lease_rejects_wrong_nonce_and_oversized_partial_messages(self):
        for data in (b'{"renew":"different"}\n', b"x" * 8193):
            read_fd, write_fd = os.pipe()
            try:
                lease = transport.Lease(read_fd, "nonce", 1, initial=data)
                with self.subTest(size=len(data)), self.assertRaises(ValueError):
                    lease.tick()
            finally:
                os.close(read_fd)
                os.close(write_fd)

    def test_request_transfer_is_bounded(self):
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"x" * 257 + b"\n")
            with patch.object(transport, "WIRE_LIMIT", 256), self.assertRaisesRegex(ValueError, "request exceeds"):
                transport.receive_request(read_fd)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_retries_require_idempotence_and_only_retry_transport_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path, result_path = root / "bundle.json", root / "result.json"
            bundle = {"spec": spec(inputs={}, outputs=[]), "files": {}, "identity": {}}
            argv = ["worker_transport.py", "relay", "--bundle", str(bundle_path), "--result", str(result_path),
                    "--attempts", "2", "--", "unused-endpoint"]
            bundle["spec"].update(idempotent=False, cacheable=False)
            bundle_path.write_text(json.dumps(bundle))
            with patch.object(sys, "argv", argv), patch.object(transport, "relay") as relay, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                transport.main()
            relay.assert_not_called()
            bundle["spec"]["idempotent"] = True
            bundle_path.write_text(json.dumps(bundle))
            with patch.object(sys, "argv", argv), patch.object(
                    transport, "relay", side_effect=[ConnectionError("lost connection"), {"complete": True}]) as relay:
                self.assertEqual(transport.main(), 0)
                self.assertEqual(relay.call_count, 2)
            result = json.loads(result_path.read_text())
            self.assertEqual(result["attempts"], 2)
            self.assertEqual(result["transport_failures"], ["lost connection"])
            with patch.object(sys, "argv", argv), patch.object(transport, "relay", return_value={"complete": False}) as relay:
                self.assertEqual(transport.main(), 1)
                self.assertEqual(relay.call_count, 1)
            with patch.object(sys, "argv", argv), patch.object(
                    transport, "relay", side_effect=ValueError("bad identity")) as relay, self.assertRaises(ValueError):
                transport.main()
            self.assertEqual(relay.call_count, 1)

    def test_relay_rejects_misbinding_and_corrupt_output(self):
        bundle = {"spec": spec(inputs={}), "files": {}, "identity": {}}
        responder = '''import json, sys
request = json.loads(sys.stdin.readline())
result = {"nonce": request["nonce"], "job_sha256": sys.argv[1], "complete": True,
          "outputs": {"output.txt": {"sha256": "0"*64, "bytes": 1, "executable": False, "data": "eA=="}}}
if sys.argv[2] == "identity":
    result["job_sha256"] = "wrong"
print(json.dumps(result), flush=True)
'''
        for case, message in (("identity", "identity mismatch"), ("output", "integrity mismatch")):
            endpoint = [sys.executable, "-c", responder, transport.job_key(bundle), case]
            with self.subTest(case=case), self.assertRaisesRegex(ValueError, message):
                transport.relay(endpoint, bundle, timeout=5)


@unittest.skipUnless(sys.platform == "linux" and shutil.which("cp"), "native transport uses Linux ELF identity")
class DetachedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pystachy-transport-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tools = {"copy": Path(shutil.which("cp")).resolve(), "python": Path(sys.executable).resolve()}
        (self.root / "input.txt").write_bytes(b"immutable native worker input\n")

    def endpoint(self, cache=False):
        argv = [sys.executable, "-I", str(SCRIPT), "serve", "--cpus", "2", "--memory-mib", "64"]
        for name, path in self.tools.items():
            argv += ["--tool", f"{name}={path}"]
        if cache:
            argv += ["--cache", str(self.root / "cache")]
        return argv

    def test_detached_native_job_roundtrip_and_cache_replay(self):
        bundle = transport.prepare(spec(), self.root, self.tools)
        first = transport.relay(self.endpoint(cache=True), bundle, timeout=10)
        second = transport.relay(self.endpoint(cache=True), bundle, timeout=10)
        self.assertTrue(first["complete"], first.get("error"))
        self.assertTrue(second["complete"], second.get("error"))
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["job_sha256"], second["job_sha256"])
        self.assertEqual(first["outputs"], second["outputs"])
        self.assertEqual(transport.unpack_file(first["outputs"]["output.txt"]), (self.root / "input.txt").read_bytes())
        self.assertGreater(first["transport"]["sent_bytes"], 0)
        self.assertGreater(first["transport"]["received_bytes"], 0)

    def test_changed_input_and_identity_are_rejected_before_execution(self):
        bundle = transport.prepare(spec(), self.root, self.tools)
        bad_input = copy.deepcopy(bundle)
        bad_input["files"]["input.txt"]["sha256"] = "0" * 64
        bad_identity = copy.deepcopy(bundle)
        bad_identity["identity"]["machine"] = "wrong-target"
        for modified, message in ((bad_input, "integrity mismatch"), (bad_identity, "identity mismatch")):
            with self.subTest(message=message):
                result = transport.relay(self.endpoint(), modified, timeout=10)
                self.assertFalse(result["complete"])
                self.assertIn(message, result["error"])
                self.assertEqual(result["commands"], [])

    @staticmethod
    def kill(process):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()

    def blocking_worker(self, lease_seconds):
        marker = self.root / "worker.pid"
        bundle = transport.prepare(spec(commands=[["@tool:python", "-c", BLOCK, str(marker)]], inputs={}, outputs=[],
                                        lease_s=lease_seconds, timeout_s=20, cacheable=False, idempotent=False),
                                   self.root, self.tools)
        process = subprocess.Popen(self.endpoint(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
        self.addCleanup(self.kill, process)
        process.stdin.write(transport.canonical({"nonce": "a" * 32, "bundle": bundle}) + b"\n")
        process.stdin.flush()
        ready = Path(str(marker) + ".ready")
        deadline = time.monotonic() + 5
        while not ready.exists():
            if process.poll() is not None:
                self.fail(f"worker exited before launch: {process.communicate()}")
            if time.monotonic() >= deadline:
                self.fail("native child did not become ready")
            time.sleep(.01)
        return process, marker

    def assert_children_gone(self, marker):
        for path in (marker, Path(str(marker) + ".child")):
            pid = int(path.read_text())
            self.assertFalse(living(pid), f"owned child {pid} survived cancellation")

    def test_input_eof_cancels_and_reaps_stubborn_children(self):
        process, marker = self.blocking_worker(2)
        process.stdin.close()
        process.stdin = None
        output, error = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 1, error)
        result = json.loads(output)
        self.assertFalse(result["complete"])
        self.assertIn("disconnected", result["error"])
        self.assert_children_gone(marker)

    def test_missing_renewal_expires_and_reaps_stubborn_children(self):
        process, marker = self.blocking_worker(1)
        process.wait(timeout=5)  # Leave stdin open: this must expire, not see EOF.
        output, error = process.communicate(timeout=1)
        self.assertEqual(process.returncode, 1, error)
        result = json.loads(output)
        self.assertFalse(result["complete"])
        self.assertIn("lease expired", result["error"])
        self.assert_children_gone(marker)


if __name__ == "__main__":
    unittest.main()
