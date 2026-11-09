"""Pystachy's JIT runner (lljit.c): its first-use build and cache (driver.jit_launcher), and lli's
contract as the driver's launch uses it, checked on small C programs rather than through the compiler.

The toolchain is PYSTACHY_LLVM's (or the driver's default); PYSTACHY_TEST_LLJIT_LLVMS adds others,
directories separated by ':' (each must hold clang, lli, llvm-as and llvm-ar), for the C API's
variants (LLVM 18 to 20, 21 to 23).
"""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.pystachy_compiler import driver  # noqa: E402

# Constructors in priority order before main, destructors after it, argv[0] the input's name, and
# main's result as the exit status
PROGRAM = r'''#include <stdio.h>
static int order[2], n;
__attribute__((constructor(200))) static void late(void) { order[n++ & 1] = 2; }
__attribute__((constructor(101))) static void early(void) { order[n++ & 1] = 1; }
__attribute__((destructor)) static void fini(void) { printf("fini\n"); }
int main(int argc, char **argv) {
  printf("%d %d %d|", n, order[0], order[1]);
  for (int i = 0; i < argc; i++) printf("[%s]", argv[i]);
  printf("\n");
  return 42;
}
'''
# A symbol that a library, an object or an archive given to the runner defines
CALLER = r'''#include <stdio.h>
int answer(void);
int main(void) { printf("%d\n", answer()); return 0; }
'''
ANSWER = "int answer(void) { return 41 + 1; }\n"
# The signals whose handlers LLVM installs in lli (llvm/lib/Support/Unix/Signals.inc), which the
# runner must leave as the process inherited them: none is caught here
SIGNALS = r'''#include <signal.h>
#include <stdio.h>
int main(void) {
  int s[] = {SIGHUP, SIGINT, SIGTERM, SIGUSR2, SIGILL, SIGTRAP, SIGABRT, SIGFPE, SIGBUS, SIGSEGV, SIGQUIT,
             SIGSYS, SIGXCPU, SIGXFSZ, SIGPIPE, SIGUSR1};
  int caught = 0;
  for (unsigned i = 0; i < sizeof s / sizeof *s; i++) {
    struct sigaction sa;
    if (!sigaction(s[i], 0, &sa) && sa.sa_handler != SIG_DFL && sa.sa_handler != SIG_IGN) caught++;
  }
  printf("%d caught\n", caught);
  return 0;
}
'''


def toolchains():
    default = os.environ.get("PYSTACHY_LLVM") or driver.llvm_dir()
    found = [default] if default else []
    for extra in os.environ.get("PYSTACHY_TEST_LLJIT_LLVMS", "").split(":"):
        if extra and extra not in found:
            found.append(extra)
    return [directory.rstrip("/") for directory in found]


@unittest.skipUnless(sys.platform == "linux", "the JIT runner is built on Linux")
class JitRunnerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="pystachy-lljit-test-")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}

    def launcher(self, llvm, *, home=ROOT, cache=None, lli=None, build=True, runner="auto"):
        # driver.jit_launcher as a run calls it: (path, "") or ("", why lli runs)
        cache = cache or self.work / "cache"
        cache.mkdir(exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=self.work))
        source = driver.hashed(str(home / "lljit.c"), {}, time.time(), False)
        try:
            return driver.jit_launcher(runner, str(home), str(cache), str(lli or Path(llvm) / "lli"), str(Path(llvm) / "clang"),
                                       source, {}, time.time(), str(tmp), tmp.name, build)
        finally:
            self.assertEqual(list(tmp.iterdir()), [], "the launcher's build left temporary files")
            tmp.rmdir()

    def compile(self, llvm, name, text, *flags):
        source = self.work / (name + ".c")
        source.write_text(text)
        output = self.work / name
        subprocess.run([str(Path(llvm) / "clang"), "-O1", *flags, str(source), "-o", str(output)], check=True,
                       capture_output=True, timeout=120)
        return str(output)

    def run_jit(self, command, *, env=None):
        return subprocess.run(command, capture_output=True, text=True, timeout=120, env=env or self.environment)

    def test_runner_behaves_as_lli(self):
        for llvm in toolchains():
            with self.subTest(llvm=llvm):
                path, why = self.launcher(llvm)
                self.assertEqual(why, "", f"{llvm}: the runner was not built")
                program = self.compile(llvm, "program", PROGRAM, "-c", "-emit-llvm")
                for level in ("-O0", "-O1", "-O2", "-O3"):
                    result = self.run_jit([path, level, "-profile-guided-section-prefix=false", program, "a b", "c"])
                    self.assertEqual((result.returncode, result.stdout, result.stderr),
                                     (42, f"2 1 2|[{program}][a b][c]\nfini\n", ""), level)
                lli = self.run_jit([str(Path(llvm) / "lli"), program, "a b", "c"])
                self.assertEqual((lli.returncode, lli.stdout), (42, f"2 1 2|[{program}][a b][c]\nfini\n"), "lli's own behavior")
                timed = self.run_jit([path, program], env=self.environment | {"PYSTACHY_TIMING": "1"})
                stages = [line.split("\t")[1] for line in timed.stderr.splitlines() if line.startswith("pystachy-timing\t")]
                self.assertEqual((timed.returncode, stages, len(timed.stderr.splitlines())),
                                 (42, ["program.jit_load", "program.jit_codegen"], 2))
                check = self.run_jit([path, "-self-check"])
                self.assertEqual((check.returncode, check.stdout), (0, "two\nlljit\n"))

    def test_inputs_and_errors(self):
        for llvm in toolchains():
            with self.subTest(llvm=llvm):
                path, why = self.launcher(llvm)
                self.assertEqual(why, "")
                caller = self.compile(llvm, "caller", CALLER, "-c", "-emit-llvm")
                library = self.compile(llvm, "libanswer.so", ANSWER, "-shared", "-fPIC")
                obj = self.compile(llvm, "answer.o", ANSWER, "-c", "-fPIC")
                archive = self.work / "libanswer.a"
                subprocess.run([str(Path(llvm) / "llvm-ar"), "rcs", str(archive), obj], check=True, timeout=60)
                for given in (f"-dlopen={library}", f"-extra-object={obj}", f"-extra-archive={archive}"):
                    for level in ("-O0", "-O2"):
                        result = self.run_jit([path, level, given, caller])
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "42\n", ""), (given, level))
                missing = self.run_jit([path, caller])
                self.assertEqual(missing.returncode, 1)
                self.assertIn("Symbols not found: [ answer ]", missing.stderr)
                self.assertTrue(missing.stderr.splitlines()[-1].startswith("lljit: "), missing.stderr)
                # (LLVM's bitcode reader writes its own error and exits: "error: file doesn't start with
                # bitcode header", as in lli, which names itself first)
                for command, text in (([path, str(archive)], "bitcode"), ([path, str(self.work / "none.bc")], "none.bc"),
                                      ([path, "-dlopen=" + str(self.work / "none.so"), caller], "none.so"), ([path], "no input file")):
                    failed = self.run_jit(command)
                    self.assertEqual((failed.returncode, failed.stdout), (1, ""), command)
                    self.assertIn(text, failed.stderr)
                # (unlike lli, an option that LLVM does not know is ignored: the C API's parser reports
                # no error; the driver passes only -profile-guided-section-prefix=false, which LLVM 18 to
                # 23 know, as lli shows)
                ignored = self.run_jit([path, "-not-an-llvm-option", f"-extra-object={obj}", caller])
                self.assertEqual((ignored.returncode, ignored.stdout, ignored.stderr), (0, "42\n", ""))
                known = self.run_jit([str(Path(llvm) / "lli"), "-profile-guided-section-prefix=false", f"-extra-object={obj}", caller])
                self.assertEqual((known.returncode, known.stdout, known.stderr), (0, "42\n", ""))

    def test_no_signal_handlers(self):
        for llvm in toolchains():
            with self.subTest(llvm=llvm):
                path, why = self.launcher(llvm)
                self.assertEqual(why, "")
                program = self.compile(llvm, "signals", SIGNALS, "-c", "-emit-llvm")
                result = self.run_jit([path, program])
                self.assertEqual((result.returncode, result.stdout), (0, "0 caught\n"))
                # (the control: lli catches them)
                control = self.run_jit([str(Path(llvm) / "lli"), program])
                self.assertNotEqual(control.stdout, "0 caught\n")
                interrupted = subprocess.run([path, program], capture_output=True, text=True, timeout=60,
                                             env=self.environment, preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_IGN))
                self.assertEqual(interrupted.stdout, "0 caught\n")

    def test_cache_entries(self):
        llvm = toolchains()[0]
        cache = self.work / "cache"
        path, why = self.launcher(llvm, cache=cache)
        self.assertEqual(why, "")
        names = sorted(entry.name for entry in cache.iterdir())
        self.assertEqual(len(names), 2, names)
        self.assertTrue(names[0].endswith(".llvm") != names[1].endswith(".llvm"), names)
        built = Path(path).stat()
        self.assertEqual(self.launcher(llvm, cache=cache), (path, ""), "found again")
        self.assertEqual(Path(path).stat().st_mtime_ns, built.st_mtime_ns, "built again")
        # what other settings and callers see: lli, without building anything
        self.assertEqual(self.launcher(llvm, cache=cache, runner="lli"), ("", "forced"))
        empty = self.work / "empty"
        self.assertEqual(self.launcher(llvm, cache=empty, build=False), ("", "program-cache"))
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual(self.launcher(llvm, cache=empty, build=False, home=self.work), ("", "no-source"))
        # a shell without ldd finds nothing it keeps: another run, which may have it, looks again
        with patch.dict(os.environ, {"PATH": str(self.work / "no-tools")}):
            self.assertEqual(self.launcher(llvm, cache=empty), ("", "no-ldd"))
        self.assertEqual(list(empty.iterdir()), [])
        # an lli that is a script (a wrapper) has no libLLVM: found once, then lli runs at once
        wrapper = self.work / "lli"
        wrapper.write_text(f"#!/bin/sh\nexec {Path(llvm) / 'lli'} \"$@\"\n")
        wrapper.chmod(0o755)
        time.sleep(2.1)  # (what is found is kept only for tools that have settled: driver.settled)
        script = self.work / "script-cache"
        self.assertEqual(self.launcher(llvm, cache=script, lli=wrapper), ("", "no-libLLVM"))
        self.assertEqual([entry.read_text() for entry in script.iterdir()], ["- no-libLLVM\n"])
        self.assertEqual(self.launcher(llvm, cache=script, lli=wrapper), ("", "no-libLLVM"))

    def test_failed_build_is_cached(self):
        llvm = toolchains()[0]
        home = self.work / "home"
        home.mkdir()
        (home / "lljit.c").write_text((ROOT / "lljit.c").read_text() + "\n#error a runner that cannot be built\n")
        os.utime(home / "lljit.c", (time.time() - 10, time.time() - 10))
        cache = self.work / "cache"
        self.assertEqual(self.launcher(llvm, home=home, cache=cache), ("", "build"))
        failures = [entry for entry in cache.iterdir() if entry.name.endswith(".fail")]
        self.assertEqual(len(failures), 1)
        self.assertIn("a runner that cannot be built", failures[0].read_text())
        started = time.monotonic()
        self.assertEqual(self.launcher(llvm, home=home, cache=cache), ("", "build"))
        self.assertLess(time.monotonic() - started, 0.25, "built again")
        # a runner that builds but fails its self-check
        (home / "lljit.c").write_text((ROOT / "lljit.c").read_text().replace('return status == 15 ? 0 : 1;', 'return 1;'))
        os.utime(home / "lljit.c", (time.time() - 10, time.time() - 10))
        self.assertEqual(self.launcher(llvm, home=home, cache=cache), ("", "self-check"))
        # (each newer entry replaced the one before)
        self.assertEqual(len([entry for entry in cache.iterdir() if entry.name.endswith(".fail")]), 1)
        # the source repaired: built and used, the failure removed
        shutil.copy(ROOT / "lljit.c", home / "lljit.c")
        os.utime(home / "lljit.c", (time.time() - 10, time.time() - 10))
        path, why = self.launcher(llvm, home=home, cache=cache)
        self.assertEqual(why, "")
        self.assertEqual(sorted(entry.name.endswith((".fail", ".llvm")) for entry in cache.iterdir()), [False, True])


if __name__ == "__main__":
    unittest.main()
