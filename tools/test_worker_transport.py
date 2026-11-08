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


STARTUP_COORDINATOR = r'''
import importlib.util, json, os, pathlib, signal, subprocess, sys, threading, time
sys.path.insert(0, sys.argv[1])
import process_workers as workers
import worker_transport as transport

root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]
shim = root / 'delayed-supervisor.py'
shim.write_text('HELPER = ' + repr(str(workers.CHILD_SCRIPT)) + '\n'
                + 'ROOT = ' + repr(str(root)) + '\nMODE = ' + repr(mode) + '\n' + r"""
import importlib.util, pathlib, sys, time
root = pathlib.Path(ROOT)
spec = importlib.util.spec_from_file_location('startup_helper', HELPER)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
if MODE == 'renew':
    time.sleep(.8)
else:
    original_send = helper._send
    def delayed_send(control, message):
        if message['event'] == 'started':
            deadline = time.monotonic() + 3
            while not (root / 'child-ready').exists():
                if time.monotonic() >= deadline:
                    raise RuntimeError('worker child did not become ready')
                time.sleep(.002)
            (root / 'readiness-held').touch()
            time.sleep(.8)
        original_send(control, message)
        if message['event'] == 'started':
            (root / 'readiness-sent').touch()
    helper._send = delayed_send
sys.exit(helper.main())
""")
workers.CHILD_SCRIPT = shim

child = """
import pathlib, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
pathlib.Path(sys.argv[1], 'child-ready').touch()
time.sleep(10)
"""
leader = """
import signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]])
time.sleep(10)
"""
queued = "import pathlib, sys; pathlib.Path(sys.argv[1], 'queued-started').touch()"
commands = [('first', [sys.executable, '-c', "print('done')"])] if mode == 'renew' else [
    ('first', [sys.executable, '-c', leader, str(root), child]),
    ('queued', [sys.executable, '-c', queued, str(root)]),
]
scope = workers.Commands(cleanup_grace=.05)
report = {'error': None, 'cancelled_before_readiness': False}
stop = threading.Event()
renewals = []
read_fd, write_fd = os.pipe()
lease = transport.Lease(read_fd, 'startup', .5)

def renew():
    while not stop.wait(.05):
        os.write(write_fd, b'{"renew":"startup"}\n')
        renewals.append(time.monotonic())

def tick():
    if mode == 'renew':
        lease.tick()
    elif (root / 'readiness-held').exists():
        report['cancelled_before_readiness'] = not (root / 'readiness-sent').exists()
        raise ConnectionError('startup callback cancelled')

thread = threading.Thread(target=renew)
if mode == 'renew':
    thread.start()
try:
    with scope:
        list(scope.run(commands, dict(os.environ), timeout=5, jobs=2, on_tick=tick))
except Exception as error:
    report['error'] = type(error).__name__ + ': ' + str(error)
finally:
    stop.set()
    if mode == 'renew':
        thread.join()
    os.close(read_fd)
    os.close(write_fd)
try:
    os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
except ChildProcessError:
    report['empty'] = True
else:
    report['empty'] = False
report['renewals_sent'] = len(renewals)
report['child_ready'] = (root / 'child-ready').exists()
report['queued_started'] = (root / 'queued-started').exists()
report['results'] = [{key: row[key] for key in ('key', 'exit_code', 'cancelled')} for row in scope.results]
print(json.dumps(report))
'''


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


@unittest.skipUnless(sys.platform == "linux", "process ownership uses Linux child subreapers")
class StartupProgressTests(unittest.TestCase):
    def run_startup(self, mode):
        with tempfile.TemporaryDirectory(prefix="pystachy-startup-") as directory:
            process = subprocess.Popen([sys.executable, "-c", STARTUP_COORDINATOR, str(SCRIPT.parent), directory, mode],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            try:
                output, error = process.communicate(timeout=8)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            self.assertEqual(process.returncode, 0, error)
            return json.loads(output)

    def test_lease_renewals_continue_during_supervisor_startup(self):
        report = self.run_startup("renew")
        self.assertIsNone(report["error"], report)
        self.assertGreaterEqual(report["renewals_sent"], 2, report)
        self.assertEqual(report["results"], [{"key": "first", "exit_code": 0, "cancelled": False}])
        self.assertTrue(report["empty"], report)

    def test_startup_callback_failure_cleans_tree_without_admitting_queued_work(self):
        report = self.run_startup("cancel")
        self.assertEqual(report["error"], "ConnectionError: startup callback cancelled", report)
        self.assertTrue(report["child_ready"], report)
        self.assertTrue(report["cancelled_before_readiness"], report)
        self.assertFalse(report["queued_started"], report)
        self.assertEqual([row["key"] for row in report["results"]], ["first"], report)
        self.assertTrue(report["results"][0]["cancelled"], report)
        self.assertTrue(report["empty"], report)


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
