"""Whole-tree completion and shutdown regressions for local process jobs.

Each scenario runs in an exclusively owned session. Handshake files prove live
child execution; zombie visibility alone is not evidence that work survived.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent

COMMON = r'''
import json, os, pathlib, signal, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import process_workers as workers
root = pathlib.Path(sys.argv[2])

def wait_file(path, timeout=5):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("handshake timed out: " + path.name)
        time.sleep(.002)

CHILD = """
import json, os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
signal.signal(signal.SIGTERM, signal.SIG_IGN)

def prove(signum, frame):
    (root / 'child-proof').write_text(str(time.monotonic()))

signal.signal(signal.SIGUSR1, prove)
(root / 'child-pid').write_text(str(os.getpid()))
(root / 'child-ready').touch()
deadline = time.monotonic() + float(sys.argv[2])
while time.monotonic() < deadline:
    time.sleep(.002)
(root / 'child-finished').write_text(str(time.monotonic()))
"""

LEADER = """
import os, pathlib, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), '1'])
deadline = time.monotonic() + 5
while not (root / 'child-ready').exists():
    if time.monotonic() >= deadline:
        raise RuntimeError('child did not start')
    time.sleep(.002)
(root / 'leader-exiting').touch()
"""
'''

RESERVATION = COMMON + r'''
limits = json.loads(sys.argv[3])
next_job = """
import os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
(root / 'next-started').touch()
try:
    os.kill(int((root / 'child-pid').read_text()), signal.SIGUSR1)
except ProcessLookupError:
    pass
deadline = time.monotonic() + .2
while not (root / 'child-proof').exists() and time.monotonic() < deadline:
    time.sleep(.002)
print(int((root / 'child-proof').exists()))
"""
request = workers.Resources(cpu=1, memory_bytes=1, input_bytes=1)
commands = [
    workers.Job('leader', [sys.executable, '-c', LEADER, CHILD, str(root)], request),
    workers.Job('next', [sys.executable, '-c', next_job, str(root)], request),
]
with workers.Commands() as scope:
    results = list(scope.run(commands, dict(os.environ), timeout=8,
                             jobs=limits.pop('jobs'), budget=workers.Budget(**limits)))
print(json.dumps({'results': results, 'peak_reserved': scope.peak_reserved}))
'''

# Delaying one real enumeration forces the reported fork-after-snapshot race.
# The hook does not fake membership, signal delivery, child liveness or results.
# Keep this seam so the same control can be rerun on the original runner. The
# subreaper implementation uses FALLBACK_SNAPSHOT at its actual KILL snapshot.
STALE_SNAPSHOT = COMMON + r'''
leader = """
import os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
(root / 'leader-ready').touch()
deadline = time.monotonic() + 5
while not (root / 'trigger-fork').exists():
    if time.monotonic() >= deadline:
        raise RuntimeError('fork not triggered')
    time.sleep(.002)
subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), '10'])
time.sleep(10)
"""
scope = workers.Commands(cleanup_grace=.05)
original = workers.group_members
cleanup_calls = 0
forced = False

def delayed_enumeration(*args, **kwargs):
    global cleanup_calls, forced
    members = original(*args, **kwargs)
    if any(state.get('cancelled') for state in scope.running.values()):
        cleanup_calls += 1
        if cleanup_calls == 2:
            (root / 'trigger-fork').touch()
            wait_file(root / 'child-ready')
            forced = True
            time.sleep(.06)
    return members

workers.group_members = delayed_enumeration
try:
    with scope:
        scope.start('leader', [sys.executable, '-c', leader, CHILD, str(root)], dict(os.environ), None)
        wait_file(root / 'leader-ready')
        raise TimeoutError('test cancellation')
except TimeoutError:
    pass
if forced:
    try:
        os.kill(int((root / 'child-pid').read_text()), signal.SIGUSR1)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + .2
    while not (root / 'child-proof').exists() and time.monotonic() < deadline:
        time.sleep(.002)
print(json.dumps({'forced': forced, 'proof': (root / 'child-proof').exists()}))
'''

FORK_ON_TERM = COMMON + r'''
leader = """
import os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
spawned = False

def terminate(signum, frame):
    global spawned
    if not spawned:
        spawned = True
        subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), '10'])

signal.signal(signal.SIGTERM, terminate)
(root / 'leader-ready').touch()
time.sleep(10)
"""
scope = workers.Commands(cleanup_grace=.1)
try:
    with scope:
        scope.start('leader', [sys.executable, '-c', leader, CHILD, str(root)], dict(os.environ), None)
        wait_file(root / 'leader-ready')
        raise TimeoutError('test cancellation')
except TimeoutError:
    pass
if (root / 'child-ready').exists():
    try:
        os.kill(int((root / 'child-pid').read_text()), signal.SIGUSR1)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + .2
    while not (root / 'child-proof').exists() and time.monotonic() < deadline:
        time.sleep(.002)
print(json.dumps({'child_started': (root / 'child-ready').exists(),
                  'proof': (root / 'child-proof').exists()}))
'''


ORPHAN_LIFETIME = COMMON + r'''
mode = sys.argv[3]
child = """
import os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
parent = os.getppid()
signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGUSR1, lambda signum, frame: (root / 'child-proof').touch())
(root / 'child-pid').write_text(str(os.getpid()))
(root / 'child-ready').touch()
while os.getppid() == parent:
    time.sleep(.002)
(root / 'leader-gone').touch()
if sys.argv[2] == 'output':
    time.sleep(.08)
    os.write(1, b'child tail\\n')
    os.write(2, b'child stderr\\n')
elif sys.argv[2] == 'overflow':
    time.sleep(.08)
    os.write(1, b'x' * 4096)
    time.sleep(10)
else:
    time.sleep(10)
"""
leader = """
import os, pathlib, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), sys.argv[3]])
while not (root / 'child-ready').exists():
    time.sleep(.002)
os.write(1, b'leader\\n')
"""
scope = workers.Commands(cleanup_grace=.15, output_limit_bytes=1024)
report = {'error': None, 'error_type': None}
try:
    with scope:
        scope.start('leader', [sys.executable, '-c', leader, child, str(root), mode],
                    dict(os.environ), None)
        wait_file(root / 'child-ready')
        wait_file(root / 'leader-gone')
        if mode == 'supervisor-death':
            os.kill(next(iter(scope.running)), signal.SIGKILL)
        next_job = workers.Job('queued', [sys.executable, '-c',
            "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(root / 'queued')])
        pending = [] if mode == 'output' else [next_job]
        for result in scope.run(pending, dict(os.environ), timeout=.4, jobs=1):
            if result['exit_code']:
                raise RuntimeError('job failed')
except (OSError, RuntimeError) as error:
    report['error'] = str(error)
    report['error_type'] = type(error).__name__
try:
    os.kill(int((root / 'child-pid').read_text()), signal.SIGUSR1)
except ProcessLookupError:
    pass
deadline = time.monotonic() + .2
while not (root / 'child-proof').exists() and time.monotonic() < deadline:
    time.sleep(.002)
report.update(results=scope.results, proof=(root / 'child-proof').exists(),
              queued=(root / 'queued').exists(), leader_gone=(root / 'leader-gone').exists())
print(json.dumps(report))
'''

FAILED_TREE = COMMON + r'''
leaf = """
import os, pathlib, signal, sys, time
root = pathlib.Path(sys.argv[1])
name = sys.argv[2]
signal.signal(signal.SIGTERM, signal.SIG_IGN)
signal.signal(signal.SIGUSR1, lambda signum, frame: (root / (name + '-proof')).touch())
(root / (name + '-pid')).write_text(str(os.getpid()))
(root / (name + '-ready')).touch()
time.sleep(10)
"""
child = """
import os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
spawned = False

def terminate(signum, frame):
    global spawned
    if not spawned:
        spawned = True
        subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), 'late-grandchild'])

signal.signal(signal.SIGTERM, terminate)
signal.signal(signal.SIGUSR1, lambda signum, frame: (root / 'child-proof').touch())
subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), 'grandchild'])
while not (root / 'grandchild-ready').exists():
    time.sleep(.002)
(root / 'child-pid').write_text(str(os.getpid()))
(root / 'child-ready').touch()
time.sleep(10)
"""
leader = """
import pathlib, subprocess, sys, time
root = pathlib.Path(sys.argv[3])
subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], str(root)])
while not (root / 'child-ready').exists():
    time.sleep(.002)
sys.exit(7)
"""
scope = workers.Commands(cleanup_grace=.2)
report = {'error': None}
commands = [
    workers.Job('failure', [sys.executable, '-c', leader, child, leaf, str(root)]),
    workers.Job('queued', [sys.executable, '-c',
        "import pathlib,sys; pathlib.Path(sys.argv[1]).touch()", str(root / 'queued')]),
]
try:
    with scope:
        for result in scope.run(commands, dict(os.environ), timeout=5, jobs=1):
            if result['exit_code']:
                raise RuntimeError('job failed')
except (OSError, RuntimeError) as error:
    report['error'] = str(error)
for name in ('child', 'grandchild', 'late-grandchild'):
    if (root / (name + '-pid')).exists():
        try:
            os.kill(int((root / (name + '-pid')).read_text()), signal.SIGUSR1)
        except ProcessLookupError:
            pass
time.sleep(.2)
report.update(results=scope.results, queued=(root / 'queued').exists(),
              late_started=(root / 'late-grandchild-ready').exists(),
              proofs=[path.name for path in root.glob('*-proof')])
print(json.dumps(report))
'''


FALLBACK_SNAPSHOT = COMMON + r'''
child = """
import os, pathlib, signal, subprocess, sys, time
root = pathlib.Path(sys.argv[2])
signal.signal(signal.SIGTERM, signal.SIG_IGN)
(root / 'child-pid').write_text(str(os.getpid()))
(root / 'child-ready').touch()
while os.getppid() != int(sys.argv[3]):
    time.sleep(.002)
(root / 'adopted').touch()
while not (root / 'trigger-fork').exists():
    time.sleep(.002)
subprocess.Popen([sys.executable, '-c', sys.argv[1], str(root), '10'])
time.sleep(10)
"""
# The late child reuses CHILD's ready/proof protocol under distinct filenames.
late_child = CHILD.replace('child-pid', 'late-pid').replace('child-ready', 'late-ready')
leader = """
import pathlib, subprocess, sys, time
root = pathlib.Path(sys.argv[3])
subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], str(root), sys.argv[4]])
while not (root / 'child-ready').exists():
    time.sleep(.002)
"""
scope = workers.Commands(cleanup_grace=.05)
original_children = workers.child_owner.direct_children
original_kill = os.kill
last_snapshot = []
forced = False
snapshot = []

def record_snapshot():
    global last_snapshot
    last_snapshot = original_children()
    return last_snapshot

def fork_after_snapshot(pid, signum):
    global forced, snapshot
    if signum == signal.SIGKILL and pid == int((root / 'child-pid').read_text()) and not forced:
        # The coordinator already chose its final KILL list. The live orphan
        # now forks a grandchild absent from that list, exactly at escalation.
        snapshot = list(last_snapshot)
        (root / 'trigger-fork').touch()
        wait_file(root / 'late-ready')
        forced = True
    return original_kill(pid, signum)

try:
    with scope:
        scope.start('leader', [sys.executable, '-c', leader, child, late_child, str(root), str(os.getpid())],
                    dict(os.environ), None)
        wait_file(root / 'child-ready')
        original_kill(next(iter(scope.running)), signal.SIGKILL)
        wait_file(root / 'adopted')
        workers.child_owner.direct_children = record_snapshot
        os.kill = fork_after_snapshot
        raise TimeoutError('cancel after supervisor loss')
except TimeoutError:
    pass
finally:
    workers.child_owner.direct_children = original_children
    os.kill = original_kill
if forced:
    try:
        os.kill(int((root / 'late-pid').read_text()), signal.SIGUSR1)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + .2
    while not (root / 'child-proof').exists() and time.monotonic() < deadline:
        time.sleep(.002)
print(json.dumps({'forced': forced, 'proof': (root / 'child-proof').exists(),
                  'snapshot': snapshot, 'original_child': int((root / 'child-pid').read_text()),
                  'late_child': int((root / 'late-pid').read_text()) if forced else None}))
'''

PREEXISTING_CHILD = COMMON + r'''
owner = workers.child_owner
before_subreaper = owner.get_subreaper()

def previous_handler(signum, frame):
    pass

before_handlers = {sig: signal.signal(sig, previous_handler) for sig in (signal.SIGINT, signal.SIGTERM)}
process = subprocess.Popen([sys.executable, '-c', CHILD, str(root), '10'])
report = {'error': None}
try:
    wait_file(root / 'child-ready')
    try:
        with workers.Commands():
            pass
    except RuntimeError as error:
        report['error'] = str(error)
    report['subreaper_unchanged'] = owner.get_subreaper() == before_subreaper
    report['handlers_unchanged'] = all(signal.getsignal(sig) is previous_handler for sig in before_handlers)
    try:
        process.send_signal(signal.SIGUSR1)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + .2
    while not (root / 'child-proof').exists() and time.monotonic() < deadline:
        time.sleep(.002)
    report['unrelated_executed'] = (root / 'child-proof').exists()
finally:
    process.kill()
    process.wait()
    for sig, handler in before_handlers.items():
        signal.signal(sig, handler)
print(json.dumps(report))
'''

RESTORE_PROCESS_STATE = COMMON + r'''
owner = workers.child_owner
original_subreaper = owner.get_subreaper()

def previous_handler(signum, frame):
    pass

original_handlers = {sig: signal.signal(sig, previous_handler) for sig in (signal.SIGINT, signal.SIGTERM)}
reports = []
try:
    for previous in (0, 1):
        owner.set_subreaper(previous)
        for mode in ('empty', 'success', 'failure'):
            scope = workers.Commands()
            failed = False
            try:
                with scope:
                    if mode != 'empty':
                        code = 'import sys; sys.exit(7)' if mode == 'failure' else 'print(42)'
                        for result in scope.run([workers.Job(mode, [sys.executable, '-c', code])],
                                                dict(os.environ), timeout=5):
                            if result['exit_code']:
                                raise RuntimeError('expected worker failure')
            except RuntimeError:
                failed = True
            try:
                os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError:
                empty = True
            else:
                empty = False
            reports.append({'previous': previous, 'mode': mode, 'failed': failed,
                            'subreaper': owner.get_subreaper(), 'empty': empty,
                            'handlers': all(signal.getsignal(sig) is previous_handler for sig in original_handlers)})
finally:
    owner.set_subreaper(original_subreaper)
    for sig, handler in original_handlers.items():
        signal.signal(sig, handler)
print(json.dumps(reports))
'''


@unittest.skipUnless(sys.platform == "linux", "local worker ownership requires Linux")
class ProcessTreeOwnershipTests(unittest.TestCase):
    def scenario(self, source, *args):
        with tempfile.TemporaryDirectory(prefix="pystachy-tree-ownership-") as temporary:
            process = subprocess.Popen(
                [sys.executable, "-c", source, str(TOOLS), temporary, *args],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                start_new_session=True,
            )
            try:
                output, error = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, error)
                return json.loads(output)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

    def test_each_admission_limit_covers_a_successful_workers_live_child(self):
        limits = [
            {"jobs": 1, "cpu": 2, "memory_bytes": 2, "input_bytes": 2},
            {"jobs": 2, "cpu": 1, "memory_bytes": 2, "input_bytes": 2},
            {"jobs": 2, "cpu": 2, "memory_bytes": 1, "input_bytes": 2},
            {"jobs": 2, "cpu": 2, "memory_bytes": 2, "input_bytes": 1},
        ]
        for limit in limits:
            with self.subTest(limit=limit):
                report = self.scenario(RESERVATION, json.dumps(limit))
                self.assertEqual([row["key"] for row in report["results"]], ["leader", "next"])
                self.assertEqual([row["exit_code"] for row in report["results"]], [0, 0])
                self.assertFalse(any(row.get("supervisor_failed", False) for row in report["results"]))
                self.assertEqual(report["results"][1]["stdout"].strip(), "0",
                                 "queued job overlapped a still-executing descendant")
                for name in ("cpu", "memory_bytes", "input_bytes"):
                    self.assertLessEqual(report["peak_reserved"][name], limit[name])

    def test_late_descendant_output_is_captured_and_hashed_completely(self):
        report = self.scenario(ORPHAN_LIFETIME, "output")
        self.assertTrue(report["leader_gone"])
        self.assertIsNone(report["error"])
        self.assertEqual(len(report["results"]), 1)
        result = report["results"][0]
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result.get("supervisor_failed", False))
        for name, expected in (("stdout", b"leader\nchild tail\n"),
                               ("stderr", b"child stderr\n")):
            self.assertEqual(result[name], expected.decode())
            self.assertEqual(result[name + "_bytes"], len(expected))
            self.assertEqual(result[name + "_hashed_bytes"], len(expected))
            self.assertEqual(result[name + "_sha256"], hashlib.sha256(expected).hexdigest())
        self.assertFalse(report["proof"])

    def test_deadline_remains_active_after_the_leader_exits(self):
        report = self.scenario(ORPHAN_LIFETIME, "deadline")
        self.assertTrue(report["leader_gone"])
        self.assertEqual(report["error_type"], "TimeoutError")
        self.assertFalse(report["queued"], "queued work started before the child finished")
        self.assertTrue(report["results"][0]["timed_out"])
        self.assertFalse(report["results"][0].get("supervisor_failed", False))
        self.assertFalse(report["proof"], "descendant survived timed-out job cleanup")

    def test_output_limit_remains_active_after_the_leader_exits(self):
        report = self.scenario(ORPHAN_LIFETIME, "overflow")
        self.assertTrue(report["leader_gone"])
        self.assertIsNotNone(report["error"])
        self.assertIn("output byte limit", report["error"])
        self.assertFalse(report["queued"], "queued work started before the child finished")
        self.assertTrue(report["results"][0]["output_limit_exceeded"])
        self.assertFalse(report["results"][0].get("supervisor_failed", False))
        self.assertFalse(report["proof"], "descendant survived oversized job cleanup")

    def test_supervisor_death_fails_closed_and_cleans_adopted_children(self):
        report = self.scenario(ORPHAN_LIFETIME, "supervisor-death")
        self.assertTrue(report["leader_gone"])
        self.assertIsNotNone(report["error"], "supervisor death was reported as job success")
        self.assertFalse(report["queued"], "queued work started after its predecessor lost ownership")
        self.assertFalse(report["proof"], "orphan survived supervisor-death cleanup")
        self.assertTrue(report["results"][0]["supervisor_failed"],
                        "supervisor protocol loss was omitted from the result")

    def test_failure_cleans_grandchildren_including_one_forked_during_term(self):
        report = self.scenario(FAILED_TREE)
        self.assertIsNotNone(report["error"])
        self.assertFalse(report["queued"])
        self.assertTrue(report["late_started"], "TERM-time fork control did not run")
        self.assertEqual(report["results"][0]["exit_code"], 7)
        self.assertFalse(report["results"][0].get("supervisor_failed", False))
        self.assertFalse(report["proofs"], "a descendant executed after failed-tree cleanup")

    def test_fork_after_last_cleanup_snapshot_cannot_escape_shutdown(self):
        supervised = (TOOLS / "process_worker_child.py").is_file()
        report = self.scenario(FALLBACK_SNAPSHOT if supervised else STALE_SNAPSHOT)
        self.assertTrue(report["forced"], "late fork control was not exercised")
        if supervised:
            self.assertIn(report["original_child"], report["snapshot"])
            self.assertNotIn(report["late_child"], report["snapshot"])
        self.assertFalse(report["proof"], "late-forked child executed after shutdown returned")

    def test_preexisting_child_is_rejected_without_touching_it(self):
        report = self.scenario(PREEXISTING_CHILD)
        self.assertIsNotNone(report["error"])
        self.assertIn("existing children", report["error"])
        self.assertTrue(report["unrelated_executed"], "scope cleanup touched an unowned child")
        self.assertTrue(report["subreaper_unchanged"])
        self.assertTrue(report["handlers_unchanged"])

    def test_subreaper_and_handlers_restore_after_every_exit_path(self):
        reports = self.scenario(RESTORE_PROCESS_STATE)
        self.assertEqual(len(reports), 6)
        for report in reports:
            with self.subTest(previous=report["previous"], mode=report["mode"]):
                self.assertEqual(report["subreaper"], report["previous"])
                self.assertTrue(report["handlers"])
                self.assertTrue(report["empty"], "scope returned without kernel-confirmed empty child set")
                self.assertEqual(report["failed"], report["mode"] == "failure")

    def test_sigterm_handler_child_cannot_execute_after_shutdown(self):
        report = self.scenario(FORK_ON_TERM)
        self.assertFalse(report["proof"], "TERM-time child executed after shutdown returned")


if __name__ == "__main__":
    unittest.main()
