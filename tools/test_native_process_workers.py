"""Native owned-process prototype: one compiled fixture, live CPython oracle.

The existing Linux Lint job runs deterministic correctness/resource checks; no
speed threshold or new CI worker is added. Run with:
  python3 -m unittest discover -s tools -p test_native_process_workers.py
"""
from pathlib import Path
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

if sys.platform == "linux":
    import fcntl
    import resource

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "tools" / "process_probes"
ORACLE = ROOT / "tools" / "rt_cpython"
LLVM = os.environ.get("PYSTACHY_LLVM", "")
HAVE_LLVM = all(shutil.which(str(Path(LLVM) / name) if LLVM else name)
                for name in ("clang", "opt", "llvm-link", "lli", "llvm-as"))


def running(pid):
    """A killed descendant can briefly be a zombie awaiting its external reaper."""
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except FileNotFoundError:
        return False


@unittest.skipUnless(sys.platform == "linux" and HAVE_LLVM, "Linux and LLVM required")
class ProcessWorkersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="pystachy-process-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.work = Path(cls.directory.name)
        cls.environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        cls.environment.update(PYSTACHY_LLVM=LLVM, PYSTACHY_CACHE=str(cls.work / "cache"),
                               PYSTACHY_IRCHECK="1", PYSTACHY_PATH=str(ROOT / "examples" / "process"),
                               PYTHONPATH=os.pathsep.join((str(ORACLE), str(ROOT / "examples" / "process"))))
        cls.compiler = [sys.executable, str(ROOT / "pystachy.py")]
        cls.owner = PROBES / "owner.py"
        cls.arguments = ["checks", sys.executable, str(PROBES / "child.py")]
        cls.binary = cls.work / "owner"
        result = subprocess.run([*cls.compiler, "build", str(cls.owner), "-o", str(cls.binary)],
                                cwd=ROOT, env=cls.environment, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.expected = cls.execute([sys.executable, str(cls.owner), *cls.arguments])
        if "False" in cls.expected or "accepted" in cls.expected:
            raise AssertionError(cls.expected)

    @classmethod
    def execute(cls, command, env=None):
        result = subprocess.run(command, cwd=ROOT, env=env or cls.environment,
                                capture_output=True, text=True, timeout=90)
        if result.returncode or result.stderr:
            raise AssertionError(f"exit {result.returncode}: {result.stderr}\n{result.stdout}")
        return result.stdout

    def test_jit_matches_cpython(self):
        self.assertEqual(self.execute([*self.compiler, "run", str(self.owner), *self.arguments]), self.expected)

    def test_aot_matches_cpython(self):
        self.assertEqual(self.execute([str(self.binary), *self.arguments]), self.expected)

    def test_aot_with_collection_on_each_allocation(self):
        env = dict(self.environment, PYSTACHY_GC_STRESS="1")
        self.assertEqual(self.execute([str(self.binary), *self.arguments], env), self.expected)

    def test_native_owner_supervises_fresh_compiler_requests(self):
        sources = [self.work / "one.py", self.work / "two.py"]
        sources[0].write_text("print(2 + 3)\n")
        sources[1].write_text("def twice(x: int) -> int:\n    return x * 2\nprint(twice(4))\n")
        output = self.execute([str(self.binary), "compile", *self.compiler, *map(str, sources)])
        directory = Path(output.strip())
        try:
            for index, source in enumerate(sources):
                expected = self.work / f"expected-{index}.ll"
                self.execute([*self.compiler, "ir", str(source), "-o", str(expected)])
                self.assertEqual((directory / f"{index}.ll").read_bytes(), expected.read_bytes())
        finally:
            shutil.rmtree(directory)

    def test_native_owner_cancels_other_requests_after_failure(self):
        marker = self.work / "blocked-child.pid"
        failing, blocked = self.work / "failing.request", self.work / "blocked.request"
        failing.write_text("fail:" + str(marker))
        blocked.write_text("block:" + str(marker))
        try:
            result = subprocess.run([str(self.binary), "compile", sys.executable,
                                     str(PROBES / "child.py"), str(failing), str(blocked)],
                                    env=self.environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("injected compiler failure", result.stderr)
            self.assertTrue(marker.exists(), "second request never ran concurrently")
            self.assert_stopped(int(marker.read_text()))
        finally:
            if marker.exists():
                pid = int(marker.read_text())
                if running(pid):
                    os.kill(pid, signal.SIGKILL)

    def test_extension_imports_and_calls_reject_native_spawning(self):
        for name, top_level in (("process_extension", False), ("process_import", True)):
            with self.subTest(top_level=top_level):
                source = self.work / (name + ".py")
                source.write_text("from ffi import export\nfrom process import Popen\n"
                                  "def _start() -> int:\n    return Popen(['/bin/true']).pid\n"
                                  "@export\ndef spawn() -> int:\n    return _start()\n"
                                  + ("_start()\nraise ValueError('import failure')\n" if top_level else ""))
                library = self.work / (name + ".so")
                self.execute([*self.compiler, "ext", str(source), "-o", str(library)])
                client = ("import importlib.util\n"
                          f"spec=importlib.util.spec_from_file_location({name!r}, {str(library)!r})\n"
                          "try:\n    module=importlib.util.module_from_spec(spec)\n"
                          "    spec.loader.exec_module(module)\n    module.spawn()\n"
                          "except NotImplementedError as error:\n"
                          "    assert 'executable or JIT owner' in str(error)\n    print('rejected')\n"
                          "else:\n    raise AssertionError('extension process spawning was accepted')\n")
                self.assertEqual(self.execute([sys.executable, "-c", client]), "rejected\n")

    def test_descriptor_closure_is_independent_of_current_soft_limit(self):
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 256:
            self.skipTest("descriptor inheritance probe needs at least 256 descriptors")
        original = os.open("/dev/null", os.O_RDONLY)
        high = fcntl.fcntl(original, fcntl.F_DUPFD, 128)
        os.close(original)
        self.addCleanup(os.close, high)
        marker = self.work / "fd-child-executed"
        source = self.work / "no-close-range.c"
        source.write_text("#include <errno.h>\n#include <unistd.h>\n"
                          "long syscall(long number, ...) { (void)number; errno=ENOSYS; return -1; }\n")
        library = self.work / "no-close-range.so"
        # This fixture's only explicit syscall() is runtime.c's close_range.
        self.execute([str(Path(LLVM) / "clang") if LLVM else "clang", "-shared", "-fPIC",
                      "-Wall", "-Wextra", "-Werror", str(source), "-o", str(library)])
        for forced_error in (False, True):
            with self.subTest(forced_error=forced_error):
                marker.unlink(missing_ok=True)
                env = dict(self.environment)
                if forced_error:
                    env["LD_PRELOAD"] = str(library)
                result = subprocess.run([str(self.binary), "fd-boundary", sys.executable,
                                         str(PROBES / "child.py"), str(high), str(marker)],
                                        env=env, capture_output=True, text=True, timeout=10, pass_fds=(high,),
                                        preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_NOFILE, (64, hard)))
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertEqual(result.stdout, "rejected before exec\n" if forced_error else "closed\nTrue True\n")
                self.assertEqual(marker.exists(), not forced_error)

    def test_sigchld_auto_reaping_is_rejected_before_fork(self):
        marker = self.work / "sigchld-child-executed"
        source = self.work / "no-child-wait.c"
        source.write_text("#include <signal.h>\n#include <unistd.h>\n"
                          "__attribute__((constructor)) static void setup(void) {\n"
                          "  struct sigaction action = {0};\n"
                          "  action.sa_handler = SIG_DFL; action.sa_flags = SA_NOCLDWAIT;\n"
                          "  sigemptyset(&action.sa_mask);\n"
                          "  if (sigaction(SIGCHLD, &action, 0)) _exit(99);\n}\n")
        library = self.work / "no-child-wait.so"
        self.execute([str(Path(LLVM) / "clang") if LLVM else "clang", "-shared", "-fPIC",
                      "-Wall", "-Wextra", "-Werror", str(source), "-o", str(library)])
        for no_wait_flag in (False, True):
            with self.subTest(no_wait_flag=no_wait_flag):
                marker.unlink(missing_ok=True)
                env = dict(self.environment)
                if no_wait_flag:
                    # exec can clear SA_NOCLDWAIT: install it in the loaded owner.
                    env["LD_PRELOAD"] = str(library)
                result = subprocess.run([str(self.binary), "sigchld", sys.executable,
                                         str(PROBES / "child.py"), str(marker)],
                                        env=env, capture_output=True, text=True, timeout=10,
                                        preexec_fn=None if no_wait_flag else
                                        lambda: signal.signal(signal.SIGCHLD, signal.SIG_IGN))
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertEqual(result.stdout, "host rejected True\n")
                self.assertFalse(marker.exists(), "child executed with unsupported automatic reaping")

    def assert_stopped(self, pid):
        deadline = time.monotonic() + 3.0
        while running(pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        if running(pid):
            os.kill(pid, signal.SIGKILL)
            self.fail(f"owned child {pid} survived owner cleanup")

    def test_descendants_end_with_their_leader(self):
        for command in ([sys.executable, str(self.owner)], [str(self.binary)]):
            with self.subTest(command=command[0]):
                output = self.execute([*command, "descendant", sys.executable, str(PROBES / "child.py")])
                pid, status = output.splitlines()
                self.assertEqual(status, "True True")
                self.assert_stopped(int(pid))

    def test_abandoned_handle_and_unhandled_exception_cleanup(self):
        for mode in ("abandon", "error"):
            with self.subTest(mode=mode):
                result = subprocess.run([str(self.binary), mode], env=self.environment,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0 if mode == "abandon" else 1, result.stderr)
                self.assert_stopped(int(result.stdout.strip()))

    def test_sigint_cleans_blocking_wait_and_owner_sleep(self):
        for mode in ("wait", "sleep"):
            with self.subTest(mode=mode):
                owner = subprocess.Popen([str(self.binary), mode], env=self.environment,
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([owner.stdout], [], [], 5.0)[0], "owner did not publish child PID")
                    pid = int(owner.stdout.readline())
                    owner.send_signal(signal.SIGINT)
                    _, stderr = owner.communicate(timeout=5.0)
                    self.assertIn(owner.returncode, (-signal.SIGINT, 130), stderr)
                    self.assert_stopped(pid)
                finally:
                    if owner.poll() is None:
                        owner.kill()
                        owner.wait(timeout=5.0)
                    owner.stdout.close()
                    owner.stderr.close()


if __name__ == "__main__":
    unittest.main()
