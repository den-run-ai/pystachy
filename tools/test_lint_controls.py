"""Failure, cancellation and launch ownership controls for hosted Lint overlap."""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import lint_controls


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ("test_*verif*.py", "test_compiler_state*.py")
PROBE = '''import os
from pathlib import Path
import signal
import subprocess
import sys
import time

assert signal.getsignal(signal.SIGINT) == signal.default_int_handler
if Path(sys.argv[0]).name == "make":  # The fake make that setUp puts first on PATH.
    assert sys.argv[1:] == ["check-fast", "lint"], sys.argv
    name = "lint"
else:
    assert sys.argv[1:-1] == ["discover", "-s", "tools", "-p"], sys.argv
    pattern = sys.argv[-1]
    assert pattern in ("test_*verif*.py", "test_compiler_state*.py"), pattern
    name = "state" if pattern == "test_compiler_state*.py" else "verification"
names = os.environ.get("LINT_SUITES", "verification,state").split(",")
root = Path.cwd()
(root / (name + ".pid")).write_text(str(os.getpid()))
if os.environ.get("LINT_BLOCK"):
    child = subprocess.Popen([sys.executable, "-c", """import sys
from pathlib import Path
import time
Path(sys.argv[1] + '.started').touch()
try:
    time.sleep(60)
except KeyboardInterrupt:
    Path(sys.argv[1] + '.signaled').touch()
""", name + ".child"])
    try:
        while not (root / (name + ".child.started")).exists():
            time.sleep(.01)
        (root / (name + ".started")).touch()
        time.sleep(60)
    except KeyboardInterrupt:
        child.wait(timeout=1)
        print(name + " canceled", flush=True)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=1)
else:
    (root / (name + ".started")).touch()
    deadline = time.monotonic() + 3
    while not all((root / (other + ".started")).exists() for other in names):
        assert time.monotonic() < deadline, "the suites did not overlap"
        time.sleep(.01)
    failed = name in os.environ.get("LINT_FAIL", "").split(",")
    if not failed:
        time.sleep(.1)  # A failing peer must not prevent this suite from finishing.
    (root / (name + ".finished")).touch()
    print(name + " complete", flush=True)
    raise SystemExit(7 if failed else 0)
'''


@unittest.skipUnless(sys.platform.startswith("linux"), "Lint runs on Linux")
class ControlTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="lint-probe-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "unittest.py").write_text(PROBE)
        make = self.root / "bin" / "make"
        make.parent.mkdir()
        make.write_text(f"#!{sys.executable}\n" + PROBE)
        make.chmod(0o755)
        self.command = [sys.executable, str(ROOT / "tools/lint_controls.py"), *PATTERNS]
        self.with_make = [sys.executable, str(ROOT / "tools/lint_controls.py"),
                          "--make", "check-fast lint", *PATTERNS]
        self.env = dict(os.environ, PATH=f"{make.parent}{os.pathsep}{os.environ.get('PATH', '')}")

    def wait_started(self, names=("state", "verification")):
        deadline = time.monotonic() + 3
        while not all((self.root / (name + ".started")).exists() for name in names):
            self.assertLess(time.monotonic(), deadline, "the suites did not start")
            time.sleep(.01)

    def clean(self):
        for path in self.root.glob("*.*"):
            if path.name != "unittest.py":
                path.unlink()

    def assert_reaped(self):
        for path in self.root.glob("*.pid"):
            with self.assertRaises(ProcessLookupError, msg=path.name):
                os.kill(int(path.read_text()), 0)

    def test_overlap_waits_for_both_and_propagates_either_failure(self):
        for failed in ("", "state", "verification", "state,verification"):
            with self.subTest(failed=failed):
                self.clean()
                result = subprocess.run(self.command, cwd=self.root,
                                        env=dict(self.env, LINT_FAIL=failed),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 7 if failed else 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["verification complete", "state complete"])
                self.assertEqual(len(list(self.root.glob("*.started"))), 2)
                self.assertEqual(len(list(self.root.glob("*.finished"))), 2)
                self.assert_reaped()

    def test_make_targets_overlap_both_suites_and_any_failure_fails(self):
        for failed in ("", "lint", "state", "lint,verification", "lint,verification,state"):
            with self.subTest(failed=failed):
                self.clean()
                result = subprocess.run(self.with_make, cwd=self.root,
                                        env=dict(self.env, LINT_FAIL=failed,
                                                 LINT_SUITES="lint,verification,state"),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 7 if failed else 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.splitlines(),
                                 ["lint complete", "verification complete", "state complete"])
                self.assertEqual(len(list(self.root.glob("*.started"))), 3)
                self.assertEqual(len(list(self.root.glob("*.finished"))), 3)
                self.assert_reaped()

    def test_suite_commands_run_make_first_and_only_when_asked(self):
        unittest_command = [sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p"]
        self.assertEqual(lint_controls.suite_commands(PATTERNS),
                         [unittest_command + [pattern] for pattern in PATTERNS])
        self.assertEqual(lint_controls.suite_commands(PATTERNS, ["check-fast", "lint"]),
                         [["make", "check-fast", "lint"]] + [unittest_command + [pattern] for pattern in PATTERNS])

    def test_cancellation_reaches_both_groups_and_reaps_the_suites(self):
        cases = [(signum, self.command, ("verification", "state")) for signum in (signal.SIGINT, signal.SIGTERM)]
        cases.append((signal.SIGTERM, self.with_make, ("lint", "verification", "state")))
        for signum, command, names in cases:
            with self.subTest(signal=signum, suites=names):
                self.clean()
                process = subprocess.Popen(command, cwd=self.root,
                                           env=dict(self.env, LINT_BLOCK="1"),
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.wait_started(names)
                    process.send_signal(signum)
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 128 + signum, stdout + stderr)
                    self.assertEqual(stdout.splitlines(), [name + " canceled" for name in names])
                    self.assertEqual(len(list(self.root.glob("*.child.signaled"))), len(names))
                    self.assert_reaped()
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)
                    for path in self.root.glob("*.pid"):
                        try:
                            os.killpg(int(path.read_text()), signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_launch_signal_is_deferred_until_child_registration_and_handlers_restore(self):
        popen = subprocess.Popen
        children = []
        previous = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}

        def launch(*args, **kwargs):
            child = popen(*args, **kwargs, cwd=self.root)
            children.append(child)
            os.kill(os.getpid(), signal.SIGTERM)
            return child

        with patch.object(lint_controls.subprocess, "Popen", side_effect=launch), redirect_stdout(io.StringIO()):
            self.assertEqual(lint_controls.run_controls(PATTERNS), 143)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)
        self.assertEqual({signum: signal.getsignal(signum) for signum in previous}, previous)

    def test_second_launch_failure_still_reaps_the_first_suite(self):
        popen = subprocess.Popen
        children = []

        def launch(*args, **kwargs):
            if children:
                raise OSError("injected second launch failure")
            child = popen(*args, **kwargs, cwd=self.root)
            children.append(child)
            return child

        with patch.object(lint_controls.subprocess, "Popen", side_effect=launch), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(OSError, "second launch failure"):
                lint_controls.run_controls(PATTERNS)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)

    def test_repeated_signals_do_not_interrupt_kill_and_reap_of_unresponsive_suites(self):
        popen, killpg = subprocess.Popen, os.killpg
        children = []

        def launch(command, **kwargs):
            name = "state" if "state" in command[-1] else "verification"
            script = ("import signal, time; from pathlib import Path; "
                      "signal.signal(signal.SIGINT, signal.SIG_IGN); "
                      f"Path({name + '.started'!r}).touch(); time.sleep(60)")
            child = popen([sys.executable, "-c", script], **kwargs, cwd=self.root)
            children.append(child)
            if len(children) == 2:
                self.wait_started()
                os.kill(os.getpid(), signal.SIGTERM)
            return child

        def interrupt_cleanup(pid, signum):
            killpg(pid, signum)
            os.kill(os.getpid(), signal.SIGINT)

        with patch.object(lint_controls.subprocess, "Popen", side_effect=launch), \
                patch.object(lint_controls.os, "killpg", side_effect=interrupt_cleanup), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(lint_controls.run_controls(PATTERNS), 143)
        self.assertEqual(len(children), 2)
        self.assertEqual([child.returncode for child in children], [-signal.SIGKILL] * 2)

    def test_more_than_two_suites_are_rejected_before_launch(self):
        for targets in ((), ("check-fast", "lint")):
            with self.subTest(targets=targets), patch.object(lint_controls.subprocess, "Popen") as launch, \
                    self.assertRaises(ValueError):
                lint_controls.run_controls([*PATTERNS, "test_extra.py"], targets)
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
