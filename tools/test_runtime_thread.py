"""Check _thread's native stack-size validation against OS rules and live CPython.

The simulated platform raises PTHREAD_STACK_MIN independently of pthread's
attribute checker, as glibc's dynamic minimum can do on Linux ARM64. Live JIT/AOT
comparisons retain platform-dependent boundary values without x86-only recordings.
"""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LLVM = os.environ.get("PYSTACHY_LLVM", "")
CLANG = shutil.which(str(Path(LLVM) / "clang") if LLVM else "clang")
HAVE_LLVM = all(shutil.which(str(Path(LLVM) / tool) if LLVM else tool)
                for tool in ("clang", "opt", "lli", "llvm-link", "llvm-as"))
PREFIX = r"""
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef int64_t I;
typedef struct { int initialized; } probe_attr_t;
#define pthread_attr_t probe_attr_t
static long probe_minimum;
static int init_error, set_error, initialized, set, destroyed;
#define PTHREAD_STACK_MIN probe_minimum
#define pthread_attr_init probe_init
#define pthread_attr_setstacksize probe_set
#define pthread_attr_destroy probe_destroy
static int probe_init(pthread_attr_t *attributes) {
  initialized++;
  attributes->initialized = !init_error;
  return init_error;
}
static int probe_set(pthread_attr_t *attributes, size_t size) {
  if (!attributes->initialized || !size) exit(2);
  set++;
  return set_error;
}
static int probe_destroy(pthread_attr_t *attributes) {
  if (!attributes->initialized) exit(3);
  destroyed++;
  return 0;
}
"""
SUFFIX = r"""
static void check(I size, long minimum, int init_fails, int set_fails, I valid,
                  int init_calls, int set_calls, int destroy_calls) {
  probe_minimum = minimum;
  init_error = init_fails; set_error = set_fails;
  initialized = set = destroyed = 0;
  if (pys_thread_stack_valid(size) != valid || initialized != init_calls ||
      set != set_calls || destroyed != destroy_calls) {
    fprintf(stderr, "incorrect stack validation: size=%lld minimum=%ld\n", (long long)size, minimum);
    exit(1);
  }
}
int main(void) {
  check(0, 65536, 1, 1, 1, 0, 0, 0);
  check(-1, 16384, 0, 0, 0, 0, 0, 0);
  check(32767, 16384, 0, 0, 0, 0, 0, 0);
  check(32768, 16384, 0, 0, 1, 1, 1, 1);
  check(32768, 65536, 0, 0, 0, 0, 0, 0);
  check(65536, 65536, 0, 0, 1, 1, 1, 1);
  check(65536, 16384, 1, 0, 0, 1, 0, 0);
  check(32769, 16384, 0, 1, 0, 1, 1, 1);
  puts("stack-size minimum, rejection and cleanup passed");
  return 0;
}
"""
PROGRAM = '''import _thread

for size in [0, 1, 32767, 32768, 32769, 65535, 65536, 131072, 1048576, 1 << 40, 1 << 62, -1]:
    _thread.stack_size(1048576)
    try:
        print(size, "ok", _thread.stack_size(size), _thread.stack_size())
    except ValueError as error:
        print(size, "error", str(error), _thread.stack_size())
_thread.stack_size(0)
'''


def validator():
    source = (ROOT / "runtime.c").read_text()
    match = re.search(r"^I pys_thread_stack_valid\(I size\) \{.*?^\}", source, re.M | re.S)
    if match is None:
        raise AssertionError("native stack-size validator is missing")
    return match[0] + "\n"


class RuntimeThreadTests(unittest.TestCase):
    @unittest.skipUnless(CLANG, "clang is required for simulated platform controls")
    def test_native_validator_handles_platform_constraints_and_cleanup(self):
        self.check_native(validator(), 0)

    @unittest.skipUnless(CLANG, "clang is required for simulated platform controls")
    def test_missing_platform_minimum_is_detected(self):
        source = validator()
        boundary = "if ((uint64_t)size < minimum) return 0;"
        self.assertIn(boundary, source)
        self.check_native(source.replace(boundary, "(void)minimum;"), 1)

    @unittest.skipUnless(CLANG, "clang is required for simulated platform controls")
    def test_ignoring_pthread_attribute_failure_is_detected(self):
        source = validator()
        self.assertIn("return !invalid;", source)
        self.check_native(source.replace("return !invalid;", "(void)invalid; return 1;"), 1)

    def check_native(self, source, expected):
        with tempfile.TemporaryDirectory(prefix="pystachy-thread-native-") as directory:
            executable = Path(directory) / "thread"
            result = subprocess.run([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", "-", "-o", str(executable)],
                                    input=PREFIX + source + SUFFIX, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 0:
                self.assertEqual(result.stdout, "stack-size minimum, rejection and cleanup passed\n")
            else:
                self.assertIn("incorrect stack validation", result.stderr)

    def test_invalid_setting_preserves_previous_value(self):
        spec = importlib.util.spec_from_file_location("thread_port", ROOT / "lib/_pystachy_thread.py")
        port = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(port)
        setattr(port, "__pys_thread_stack_valid", lambda size: size == 0 or size >= 65536)
        self.assertEqual(port.stack_size(131072), 0)
        with self.assertRaisesRegex(ValueError, "size not valid: 32768 bytes"):
            port.stack_size(32768)
        self.assertEqual(port.stack_size(65536), 131072)
        self.assertEqual(port.stack_size(0), 65536)
        self.assertEqual(port.stack_size(), 0)

    @unittest.skipUnless(HAVE_LLVM, "complete LLVM is required for native JIT/AOT oracle checks")
    def test_jit_and_aot_match_live_cpython_at_platform_edges(self):
        with tempfile.TemporaryDirectory(prefix="pystachy-thread-oracle-") as directory:
            work = Path(directory)
            program = work / "thread_edges.py"
            program.write_text(PROGRAM)
            environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            environment.update(PYSTACHY_LLVM=LLVM, PYSTACHY_CACHE=str(work / "cache"), PYSTACHY_IRCHECK="1")
            oracle = subprocess.run([sys.executable, str(program)], capture_output=True, text=True,
                                    env=environment, timeout=30)
            self.assertEqual(oracle.returncode, 0, oracle.stderr)
            self.assertEqual(oracle.stderr, "")
            compiler = [sys.executable, str(ROOT / "pystachy.py")]
            jit = subprocess.run([*compiler, "run", str(program)], cwd=ROOT, capture_output=True, text=True,
                                 env=environment, timeout=90)
            self.assertEqual(jit.returncode, 0, jit.stderr)
            self.assertEqual(jit.stderr, "")
            self.assertEqual(jit.stdout, oracle.stdout)
            executable = work / "thread_edges"
            build = subprocess.run([*compiler, "build", str(program), "-o", str(executable)], cwd=ROOT,
                                   capture_output=True, text=True, env=environment, timeout=90)
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertEqual(build.stderr, "")
            aot = subprocess.run([str(executable)], capture_output=True, text=True, env=environment, timeout=30)
            self.assertEqual(aot.returncode, 0, aot.stderr)
            self.assertEqual(aot.stderr, "")
            self.assertEqual(aot.stdout, oracle.stdout)

    def test_primitive_is_private_to_shipped_thread_module(self):
        with tempfile.TemporaryDirectory(prefix="pystachy-thread-private-") as directory:
            program = Path(directory) / "private.py"
            program.write_text("print(__pys_thread_stack_valid(32768))\n")
            result = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(program),
                                     "-o", str(Path(directory) / "private.ll")], cwd=ROOT,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1)
            self.assertIn("name '__pys_thread_stack_valid' is not defined", result.stderr)


if __name__ == "__main__":
    unittest.main()
