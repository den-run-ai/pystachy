"""Deadline and completion supervision while a replacement worker starts.

Real children and held supervisor heartbeats exercise overlap. Isolated
coordinators and outer timeouts contain a broken ownership implementation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parent

COMMON = r"""
import json, os, pathlib, signal, subprocess, sys, threading, time, types
sys.path.insert(0, sys.argv[1])
import process_workers as workers
root = pathlib.Path(sys.argv[2])
mode = sys.argv[3]


def wait_file(path, timeout=4):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError('handshake timed out: ' + path.name)
        time.sleep(.002)


def wait_finished(pid, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except ChildProcessError:
            return  # The coordinator already collected the same completion.
        if status is not None:
            return
        time.sleep(.002)
    raise RuntimeError('supervisor did not finish')


scope = workers.Commands(cleanup_grace=.05, output_limit_bytes=1024)
report = {'error': None, 'error_type': None, 'yielded': []}
"""

OVERLAP = (
    COMMON
    + r'''
# A replacement helper waits before sending its real startup heartbeat. Its
# command cannot execute until the controller explicitly releases this gate.
helper = root / 'held_helper.py'
helper.write_text("""
import os, pathlib, runpy, signal, sys, time
if os.environ.get('PYSTACHY_TEST_HOLD_STARTUP'):
    root = pathlib.Path(os.environ['PYSTACHY_TEST_ROOT'])
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT, signal.SIGTERM})
    (root / 'startup-held').touch()
    deadline = time.monotonic() + 4
    while not (root / 'release-startup').exists():
        if time.monotonic() >= deadline:
            raise RuntimeError('startup gate was not released')
        time.sleep(.002)
runpy.run_path(""" + repr(str(workers.CHILD_SCRIPT)) + """, run_name='__main__')
""")
workers.CHILD_SCRIPT = helper
victim = """
import os, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
(root / 'victim-ready').touch()
while not (root / 'startup-held').exists():
    time.sleep(.002)
mode = sys.argv[2]
if mode == 'deadline':
    while not (root / 'release-victim').exists():
        time.sleep(.002)
elif mode == 'output':
    os.write(1, b'x' * 4096)
    (root / 'overflow-written').touch()
    time.sleep(10)
elif mode == 'failure':
    sys.exit(7)
print('victim done')
"""
short = """
import pathlib, sys, time
root = pathlib.Path(sys.argv[1])
while not (root / 'victim-ready').exists():
    time.sleep(.002)
time.sleep(float(sys.argv[2]))
"""
mark = "import pathlib,sys; pathlib.Path(sys.argv[1]).touch(); print(sys.argv[2])"
env = dict(os.environ)
held_env = dict(env, PYSTACHY_TEST_HOLD_STARTUP='1', PYSTACHY_TEST_ROOT=str(root))
timeout = 1.2 if mode == 'deadline' else 4
commands = [
    workers.Job('victim', [sys.executable, '-c', victim, str(root), mode]),
    workers.Job('short', [sys.executable, '-c', short, str(root), '.6' if mode == 'deadline' else '0']),
    workers.Job('replacement', [sys.executable, '-c', mark, str(root / 'replacement-started'), 'replacement'],
                env=held_env),
]
if mode == 'failure':
    commands.append(workers.Job('queued', [sys.executable, '-c', mark, str(root / 'queued-started'), 'queued']))
stop = threading.Event()
controller_errors = []
victim_state = []
original_start = scope.start


def remember_start(*args, **kwargs):
    original_start(*args, **kwargs)
    if args[0] == 'victim':
        victim_state.append(next(state for state in scope.running.values() if state['key'] == 'victim'))


scope.start = remember_start


def release():
    try:
        wait_file(root / 'startup-held')
        first = victim_state[0]
        if mode == 'deadline':
            # Complete the first command only after its absolute deadline;
            # the replacement still has ample time inside its own limit.
            if stop.wait(max(0, first['start'] + timeout + .1 - time.monotonic())):
                return
            (root / 'release-victim').touch()
            wait_finished(first['process'].pid)
        elif mode == 'output':
            wait_file(root / 'overflow-written')
            # A working callback detects overflow without this heartbeat.
            # The old scheduler needs the gate released before it notices.
            if stop.wait(.5):
                return
        else:
            wait_finished(first['process'].pid)
        if not stop.is_set():
            (root / 'release-startup').touch()
    except Exception as error:
        if not stop.is_set():
            controller_errors.append(str(error))
            (root / 'release-startup').touch()


controller = threading.Thread(target=release, daemon=True)
try:
    with scope:
        controller.start()
        try:
            for result in scope.run(commands, env, timeout=timeout, jobs=2):
                report['yielded'].append(result['key'])
                if result['exit_code']:
                    raise RuntimeError('command failed: ' + result['key'])
        except BaseException:
            stop.set()
            raise
except (OSError, RuntimeError) as error:
    report['error'], report['error_type'] = str(error), type(error).__name__
finally:
    stop.set()
    controller.join(timeout=5)
report.update(results=scope.results, held=(root / 'startup-held').exists(),
              startup_released=(root / 'release-startup').exists(),
              replacement_started=(root / 'replacement-started').exists(),
              queued_started=(root / 'queued-started').exists(),
              controller_errors=controller_errors, controller_alive=controller.is_alive())
try:
    os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
except ChildProcessError:
    report['children_reaped'] = True
else:
    report['children_reaped'] = False
print(json.dumps(report))
'''
)

LATE_OBSERVATION = (
    COMMON
    + r"""
original_time = workers.time
try:
    with scope:
        if mode == 'completion':
            scope.start('late', [sys.executable, '-c', 'print(42)'], dict(os.environ), None)
            pid, state = next(iter(scope.running.items()))
            wait_finished(pid)
            # Model a descheduled coordinator resuming with an already-waitable
            # completion after the deadline. The kernel completion is real.
            expired = state['start'] + 6
            workers.time = types.SimpleNamespace(monotonic=lambda: expired, sleep=time.sleep)
            list(scope.run([], dict(os.environ), timeout=5))
        else:
            read_control = scope.read_control

            def delayed_heartbeat(state):
                read_control(state)
                if state['started']:
                    expired = state['start'] + 6
                    workers.time = types.SimpleNamespace(monotonic=lambda: expired, sleep=time.sleep)
                    report['heartbeat_observed'] = True

            scope.read_control = delayed_heartbeat
            scope.start('late', [sys.executable, '-c', 'print(42)'], dict(os.environ), None, timeout=5)
except (OSError, RuntimeError) as error:
    report['error'], report['error_type'] = str(error), type(error).__name__
finally:
    workers.time = original_time
report['results'] = scope.results
print(json.dumps(report))
"""
)


CALLER_PAUSE = (
    COMMON
    + r"""
original_popen = subprocess.Popen
launches = []
marker = root / 'replacement-started'


def launch(*args, **kwargs):
    process = original_popen(*args, **kwargs)
    launches.append(process.pid)
    if len(launches) == 3:
        # If admitted, let the real command publish proof before returning.
        # A later callback rejection cannot hide the admission side effect.
        wait_file(marker)
    return process


workers.subprocess.Popen = launch
ready = root / 'second-ready'
short = '''
import pathlib, sys, time
ready = pathlib.Path(sys.argv[1])
while not ready.exists():
    time.sleep(.002)
'''
second = 'import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(10)'
commands = [
    workers.Job('short', [sys.executable, '-c', short, str(ready)]),
    workers.Job('deadline', [sys.executable, '-c', second, str(ready)]),
    workers.Job('replacement', [sys.executable, '-c',
        'import pathlib,sys; pathlib.Path(sys.argv[1]).touch()', str(marker)]),
]
try:
    with scope:
        for result in scope.run(commands, dict(os.environ), timeout=.5, jobs=2):
            report['yielded'].append(result['key'])
            if result['key'] == 'short':
                time.sleep(.6)
except (OSError, RuntimeError) as error:
    report['error'], report['error_type'] = str(error), type(error).__name__
report.update(results=scope.results, launches=len(launches), replacement_started=marker.exists())
print(json.dumps(report))
"""
)


@unittest.skipUnless(sys.platform == "linux", "local worker supervision requires Linux")
class StartupSupervisionTests(unittest.TestCase):
    def scenario(self, source, mode):
        with tempfile.TemporaryDirectory(
            prefix="pystachy-startup-supervision-"
        ) as temporary:
            process = subprocess.Popen(
                [sys.executable, "-c", source, str(TOOLS), temporary, mode],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            try:
                output, error = process.communicate(timeout=12)
                self.assertEqual(process.returncode, 0, error)
                return json.loads(output)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)

    def overlap(self, mode):
        report = self.scenario(OVERLAP, mode)
        self.assertTrue(report["held"], "replacement startup was not held")
        self.assertFalse(
            report["controller_alive"], "test controller survived the scenario"
        )
        self.assertEqual(report["controller_errors"], [])
        self.assertTrue(report["children_reaped"], "scope returned with owned children")
        return report

    def test_running_deadline_remains_active_during_replacement_startup(self):
        report = self.overlap("deadline")
        self.assertEqual(report["error_type"], "TimeoutError", report)
        victim = next(row for row in report["results"] if row["key"] == "victim")
        self.assertTrue(victim["timed_out"], "overdue job was accepted as successful")
        self.assertNotIn("victim", report["yielded"])
        self.assertFalse(
            report["startup_released"],
            "deadline was checked only after startup resumed",
        )
        self.assertFalse(
            report["replacement_started"], "replacement ran after the existing deadline"
        )

    def test_live_output_limit_interrupts_replacement_startup(self):
        report = self.overlap("output")
        self.assertIn("output byte limit", report["error"] or "", report)
        victim = next(row for row in report["results"] if row["key"] == "victim")
        self.assertTrue(victim["output_limit_exceeded"])
        self.assertFalse(
            report["startup_released"],
            "output limit was checked only after startup resumed",
        )
        self.assertFalse(
            report["replacement_started"], "startup masked the existing output overflow"
        )

    def test_timely_completion_is_delivered_once_during_startup_overlap(self):
        report = self.overlap("success")
        self.assertIsNone(report["error"], report)
        self.assertEqual(report["yielded"], ["short", "victim", "replacement"])
        self.assertEqual([row["key"] for row in report["results"]], report["yielded"])
        self.assertTrue(
            all(
                row["exit_code"] == 0 and not row["timed_out"]
                for row in report["results"]
            )
        )

    def test_failure_observed_during_startup_prevents_further_admission(self):
        report = self.overlap("failure")
        self.assertEqual(report["error"], "command failed: victim", report)
        self.assertIn("victim", report["yielded"])
        self.assertFalse(
            report["queued_started"],
            "queued work started before caller rejected failure",
        )

    def test_caller_pause_cannot_admit_work_after_an_existing_deadline(self):
        report = self.scenario(CALLER_PAUSE, "caller")
        self.assertEqual(report["yielded"], ["short"], report)
        self.assertEqual(report["error_type"], "TimeoutError", report)
        self.assertEqual(
            report["launches"], 2, "replacement was spawned after the existing deadline"
        )
        self.assertFalse(report["replacement_started"])
        victim = next(row for row in report["results"] if row["key"] == "deadline")
        self.assertTrue(victim["timed_out"])

    def test_waitable_completion_cannot_bypass_expired_deadline(self):
        report = self.scenario(LATE_OBSERVATION, "completion")
        self.assertEqual(report["error_type"], "TimeoutError", report)
        self.assertTrue(report["results"][0]["timed_out"])

    def test_late_startup_heartbeat_cannot_bypass_startup_deadline(self):
        report = self.scenario(LATE_OBSERVATION, "heartbeat")
        self.assertTrue(
            report.get("heartbeat_observed"),
            "startup heartbeat control was not exercised",
        )
        self.assertEqual(report["error_type"], "TimeoutError", report)
        self.assertTrue(report["results"][0]["timed_out"])


if __name__ == "__main__":
    unittest.main()
