"""The optional netio differential gate must be independent, bounded and fail closed."""

import contextlib
import copy
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import selectors
import shlex
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("netio_check", ROOT / "examples/netio/check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def passed_report(cpython_only=False):
    modes = list(check.CPYTHON_MODES + (() if cpython_only else check.NATIVE_MODES))
    return {"schema": 1, "result": "pass", "python": (ROOT / ".python-version").read_text().strip(),
            "cases": list(check.CASES), "modes": modes, "repeat": 2,
            "runs": {mode: {"cases": list(check.CASES)} for mode in modes}}


class CheckerTests(unittest.TestCase):
    def test_hosted_compiler_runs_from_private_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            command = check.compiler_command(shlex.join([sys.executable, "pystachy.py"]))
            result = check.run("hosted/version", command + ["--version"],
                               check.environment(directory), directory)
            self.assertIn((ROOT / "VERSION").read_text().strip().encode(), result.stdout)
            self.assertEqual(result.stderr, b"")

    def test_relative_executable_with_spaces_runs_from_private_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            executable = directory / "compiler with spaces"
            executable.write_text(f"#!{sys.executable}\nprint('compiler control')\n")
            executable.chmod(0o755)
            work = directory / "private"
            work.mkdir()
            with mock.patch.object(check, "ROOT", directory):
                command = check.compiler_command(shlex.join(["./compiler with spaces"]))
            result = check.run("native/path", command, os.environ.copy(), work)
            self.assertEqual(result.stdout, b"compiler control\n")
            self.assertEqual(result.stderr, b"")

    def test_compiler_command_preserves_python_module_and_code_arguments(self):
        for flag, argument in (("-m", "pystachy"), ("-c", "pystachy.py")):
            with self.subTest(flag=flag):
                command = check.compiler_command(shlex.join([sys.executable, flag, argument]))
                self.assertEqual(command[1:], [flag, argument])
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            check.compiler_command(" ")

    def test_oracle_uses_unmodified_stdlib_implementations(self):
        spec = importlib.util.spec_from_file_location("netio_oracle", check.HERE / "oracle/netio.py")
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        self.assertIs(oracle.socket, socket.socket)
        self.assertIs(oracle.socketpair, socket.socketpair)
        self.assertIs(oracle.DefaultSelector, selectors.DefaultSelector)
        self.assertIs(oracle.SelectorKey, selectors.SelectorKey)
        self.assertIs(oracle.read, os.read)
        self.assertIs(oracle.set_blocking, os.set_blocking)
        self.assertIs(oracle.close_fd, os.close)

    def test_real_oracle_exercises_every_case(self):
        self.assertEqual(len(set(check.CASES)), len(check.CASES))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "probe.py"
            source.write_bytes(check.SOURCE.read_bytes())
            env = check.environment(directory, oracle=True)
            for case in check.CASES:
                with self.subTest(case=case):
                    result = check.scenario("oracle/" + case, [sys.executable, str(source)],
                                            case, 1, env, directory, 10)
                    self.assertEqual(result.stdout, f"{case} 1 ok\n".encode())
                    self.assertEqual(result.stderr, b"")

    def test_tcp_probe_accepts_nonzero_option_and_rejects_wrong_states(self):
        spec = importlib.util.spec_from_file_location("netio_oracle", check.HERE / "oracle/netio.py")
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        spec = importlib.util.spec_from_file_location("netio_probe", check.SOURCE)
        probe = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"netio": oracle}):
            spec.loader.exec_module(probe)

        class FlagSocket(socket.socket):
            enabled_result = 4
            disabled_result = 0

            def getsockopt(self, level, option):
                value = super().getsockopt(level, option)
                if (level, option) == (socket.SOL_SOCKET, socket.SO_REUSEADDR):
                    return self.enabled_result if value else self.disabled_result
                return value

        with mock.patch.object(oracle, "socket", FlagSocket):
            probe.tcp(1)
            for enabled, disabled in ((0, 0), (4, 4)):
                with self.subTest(enabled=enabled, disabled=disabled):
                    FlagSocket.enabled_result = enabled
                    FlagSocket.disabled_result = disabled
                    with self.assertRaisesRegex(AssertionError, "SO_REUSEADDR"):
                        probe.tcp(1)

    def test_refused_fixture_releases_port_and_rejects_invalid_completion(self):
        spec = importlib.util.spec_from_file_location("netio_oracle", check.HERE / "oracle/netio.py")
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        spec = importlib.util.spec_from_file_location("netio_probe", check.SOURCE)
        probe = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"netio": oracle}):
            spec.loader.exec_module(probe)
        created = []
        test = self

        class CheckedSocket(socket.socket):
            def __init__(self):
                super().__init__()
                created.append(self)

            def connect_ex(self, address):
                test.assertEqual(created[0].fileno(), -1, "reservation must close before connect")
                test.assertNotEqual(self.getsockname()[1], 0, "client must reserve its source port")
                test.assertNotEqual(self.getsockname()[1], address[1], "endpoint ports must differ")
                return super().connect_ex(address)

        with mock.patch.object(oracle, "socket", CheckedSocket):
            probe.refused(1)
            key = selectors.SelectorKey(None, -1, selectors.EVENT_WRITE, 1)
            ready = [(key, selectors.EVENT_WRITE)]
            for result, events, error in ((0, ready, 0),
                                           (errno.EINPROGRESS, [], errno.ECONNREFUSED),
                                           (errno.EINPROGRESS, ready, 0)):
                with self.subTest(result=result, events=events, error=error), \
                        mock.patch.object(CheckedSocket, "connect_ex", return_value=result), \
                        mock.patch.object(CheckedSocket, "getsockopt", return_value=error), \
                        mock.patch.object(oracle, "DefaultSelector") as selector:
                    selector.return_value.select.return_value = events
                    with self.assertRaises(AssertionError):
                        probe.refused(1)

    def test_environment_excludes_inherited_compiler_and_python_overrides(self):
        dirty = {"PYSTACHY_LLVM": "/llvm", "PYSTACHY_HOME": "/foreign", "PYSTACHY_PATH": "/foreign",
                 "PYSTACHY_GC_STRESS": "1", "PYSTACHY_GC_STRESS_PROGRAM": "1", "PYSTACHY_JOBS": "99",
                 "PYTHONPATH": "/foreign", "PYTHONHOME": "/foreign", "PYTHONOPTIMIZE": "2", "PATH": "/bin"}
        with mock.patch.dict(os.environ, dirty, clear=True):
            env = check.environment(Path("/private"))
            oracle = check.environment(Path("/private"), oracle=True)
            self.assertEqual(dict(os.environ), dirty)
        self.assertEqual(env["PYSTACHY_LLVM"], "/llvm")
        self.assertEqual(env["PYSTACHY_HOME"], str(ROOT))
        self.assertEqual(env["PYSTACHY_PATH"], str(check.HERE))
        self.assertEqual(env["PYSTACHY_CACHE"], "/private/cache")
        self.assertEqual(env["PYSTACHY_PROGRAM_CACHE"], "0")
        self.assertEqual(env["PYSTACHY_JOBS"], "2")
        self.assertEqual(env["LD_LIBRARY_PATH"], "/private")
        self.assertEqual(oracle["PYTHONPATH"], str(check.HERE / "oracle"))
        self.assertNotIn("rt_cpython", oracle["PYTHONPATH"])
        for key in ("PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM", "PYTHONHOME", "PYTHONOPTIMIZE"):
            self.assertNotIn(key, env)

    def test_runner_keeps_diagnostics_and_rejects_nonzero_status(self):
        command = [sys.executable, "-c", "import os; os.write(1,b'\\xff\\n'); os.write(2,b'diagnostic\\n')"]
        result = check.run("binary/aot", command, os.environ.copy(), ROOT)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"\xff\n", b"diagnostic\n"))
        with self.assertRaisesRegex(RuntimeError, "exit=3") as caught:
            check.run("binary/aot", command[:-1] + [command[-1] + "; exit(3)"], os.environ.copy(), ROOT)
        self.assertIn("diagnostic", str(caught.exception))

    def test_timeout_kills_owned_grandchildren_and_keeps_partial_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "survived"
            child = "import pathlib,sys,time; time.sleep(2); pathlib.Path(sys.argv[1]).touch()"
            script = ("import subprocess,sys,time; "
                      f"subprocess.Popen([sys.executable,'-c',{child!r},sys.argv[1]]); "
                      "print('started',flush=True); print('pending',file=sys.stderr,flush=True); time.sleep(30)")
            with self.assertRaises(RuntimeError) as caught:
                check.run("timeout/jit", [sys.executable, "-c", script, str(marker)],
                          os.environ.copy(), ROOT, timeout=0.2)
            for word in ("timeout/jit", "exit=timeout", "started", "pending"):
                self.assertIn(word, str(caught.exception))
            self.assertFalse(marker.exists())

    def test_drain_notification_timeout_handles_partial_lines(self):
        spec = importlib.util.spec_from_file_location("netio_check_drain", check.HERE / "check_drain.py")
        consumer = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {"check": check}):
            spec.loader.exec_module(consumer)
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"partial")
            with os.fdopen(read_fd, "rb", buffering=0) as stream:
                with self.assertRaisesRegex(RuntimeError, "no complete pipe notification"):
                    consumer.first_line(stream, 0.03)
        finally:
            os.close(write_fd)

    def test_comparison_is_exact_for_status_stdout_and_stderr(self):
        reference = subprocess.CompletedProcess(["oracle"], 0, b"ok\n", b"")
        for status, stdout, stderr in ((1, b"ok\n", b""), (0, b"ok", b""),
                                       (0, b"ok\nextra", b""), (0, b"ok\n", b"warning")):
            with self.subTest(status=status, stdout=stdout, stderr=stderr), self.assertRaisesRegex(ValueError, "differs"):
                check.compare("tcp/jit", subprocess.CompletedProcess(["native"], status, stdout, stderr), reference)
        check.compare("same", reference, reference)

    def test_inherited_pipe_has_high_descriptor_and_closes_on_failure(self):
        with self.assertRaisesRegex(RuntimeError, "fixture consumer failed"):
            with check.inherited_pipe() as fd:
                self.assertGreater(fd, 1024)
                self.assertEqual(os.read(fd, 64), b"hi\x00\xff\n")
                self.assertEqual(os.read(fd, 1), b"")
                raise RuntimeError("fixture consumer failed")
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_c_build_requires_output_and_uses_strict_warnings(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with mock.patch.object(check, "run", return_value=subprocess.CompletedProcess(["cc"], 0, b"", b"")) as run:
                with self.assertRaisesRegex(ValueError, "did not create"):
                    check.build_bridge(directory, {}, ["test-cc"], 3)
                command = run.call_args.args[1]
                for flag in ("-std=c11", "-Wall", "-Wextra", "-Werror", "-Wpedantic", "-fPIC"):
                    self.assertIn(flag, command)
                self.assertEqual(run.call_args.kwargs["timeout"], 3)
            for stdout, stderr in ((b"warning", b""), (b"", b"warning")):
                with self.subTest(stdout=stdout, stderr=stderr), mock.patch.object(check, "run", return_value=
                        subprocess.CompletedProcess(["cc"], 0, stdout, stderr)), self.assertRaisesRegex(ValueError, "diagnostics"):
                    check.build_bridge(directory, {}, ["cc"], 3)

    def test_old_success_is_replaced_before_failed_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(json.dumps(passed_report()))

            def fail(args, report):
                self.assertEqual(json.loads(path.read_text())["result"], "running")
                raise RuntimeError("jit/recv: wrong bytes")

            with mock.patch.object(check, "check", side_effect=fail), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check.main(["--json", str(path)]), 1)
            report = json.loads(path.read_text())
            self.assertEqual(report["result"], "fail")
            self.assertEqual(report["cases"], [])
            self.assertIn("wrong bytes", report["error"])

    def test_reports_reject_missing_modes_cases_or_false_pass(self):
        check.validate_report(passed_report())
        check.validate_report(passed_report(True), True)
        mutations = [lambda r: r.update(schema=True), lambda r: r.update(result="running"),
                     lambda r: r.update(python="3.12.0"), lambda r: r.update(repeat=False),
                     lambda r: r["modes"].pop(), lambda r: r["cases"].pop(),
                     lambda r: r["cases"].append(r["cases"][0]), lambda r: r["runs"].pop("jit_gc"),
                     lambda r: r["runs"]["aot"]["cases"].pop(), lambda r: r.update(error="skipped")]
        for mutate in mutations:
            report = copy.deepcopy(passed_report())
            mutate(report)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                check.validate_report(report)
        with self.assertRaises(ValueError):
            check.validate_report(passed_report(True))


class PrototypeBoundaryTests(unittest.TestCase):
    def test_unsupported_scope_and_failed_registration_leave_no_resources(self):
        # These are explicit prototype restrictions, not stdlib parity claims.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            env = check.environment(directory)
            check.build_bridge(directory, env, check.c_compiler(None, env), 30)
            program = '''
import os
import netio

def rejects(kind, call):
    try:
        call()
    except kind:
        return
    raise AssertionError("operation was accepted")

before = len(os.listdir("/proc/self/fd" if os.sys.platform == "linux" else "/dev/fd"))
assert netio.MAX_RECEIVE == 16777216
assert netio.MAX_REGISTRATIONS == 4096
left, right = netio.socketpair()
try:
    rejects(ValueError, lambda: left.recv(-1))
    rejects(ValueError, lambda: left.recv(netio.MAX_RECEIVE + 1))
    rejects(ValueError, lambda: netio.read(left.fileno(), -1))
    rejects(ValueError, lambda: netio.read(left.fileno(), netio.MAX_RECEIVE + 1))
    rejects(NotImplementedError, lambda: left.settimeout(0.1))
    rejects(NotImplementedError, lambda: netio.socket(netio.AF_UNIX))
    rejects(NotImplementedError, lambda: netio.socketpair(netio.AF_INET))
    rejects(NotImplementedError, lambda: left.bind(("localhost", 0)))
    rejects(OverflowError, lambda: left.bind(("127.0.0.1", 65536)))
    rejects(ValueError, lambda: left.settimeout(-1.0))
    with netio.DefaultSelector() as selector:
        rejects(ValueError, lambda: selector.select(float("nan")))
        rejects(OverflowError, lambda: selector.select(float("inf")))
        selector.register(left, netio.EVENT_READ)
        rejects(ValueError, lambda: selector.modify(left, 4))
        assert selector.get_key(left).events == netio.EVENT_READ
        netio.MAX_REGISTRATIONS = 1
        rejects(ValueError, lambda: selector.register(right, netio.EVENT_READ))
        netio.MAX_REGISTRATIONS = 4096
        rejects(KeyError, lambda: selector.get_key(right))
        selector.unregister(left)
        oldfd = left.fileno()
        left.close()
        rejects(OSError, lambda: selector.register(oldfd, netio.EVENT_READ))
        rejects(KeyError, lambda: selector.get_key(oldfd))
    rejects(ValueError, lambda: selector.select(0.0))
finally:
    left.close()
    right.close()
assert len(os.listdir("/proc/self/fd" if os.sys.platform == "linux" else "/dev/fd")) == before
print("prototype boundaries ok")
'''
            result = check.run("boundaries/cpython_bridge", [sys.executable, "-c", program], env, directory)
            self.assertEqual(result.stdout, b"prototype boundaries ok\n")
            self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
