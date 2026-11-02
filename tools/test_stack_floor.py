"""The native stack's floor (#1015): deep recursion under a raised sys.setrecursionlimit().

A counted entry whose stack pointer is below the floor raises RecursionError before the thread's
stack runs out, so that except and finally blocks run and buffered output survives, in JIT and
AOT. The floor's policy (runtime.c's stack_floor) is checked natively against simulated pthread
bounds, with negative controls. Live programs then run as subprocesses under a fixed stack limit
(RLIMIT_STACK), without core dumps and with time limits, normally and with program GC stress:
a recursion that fits matches CPython, and one that does not pins the documented deviation
(docs/language/compatibility.md#errors-and-control-flow), where CPython, whose Python frames
live on the heap, completes.
"""

import os
from pathlib import Path
import platform
import re
import resource
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
GLIBC = sys.platform == "linux" and platform.libc_ver()[0] == "glibc"
KIB = 1024
MIB = 1024 * KIB
STACK_ERROR = "RecursionError: maximum recursion depth exceeded (the native stack is nearly full)"

PREFIX = r"""
#define _GNU_SOURCE
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/resource.h>
#include <unistd.h>
typedef int64_t I;
static I pys_recursion_state[3];
/* simulated: the main thread's file name (AT_EXECFN), its stack limit, the page size and the
   pthread bounds; got counts pthread_getattr_np calls, destroyed pthread_attr_destroy calls */
static const char *execfn;
static rlim_t limit;
static int getattr_error, getstack_error, got, destroyed;
static uintptr_t mock_lo, mock_size;
static unsigned long probe_getauxval(unsigned long type) { return type == AT_EXECFN ? (unsigned long)execfn : 0; }
static int probe_getrlimit(int resource, struct rlimit *rl) {
  if (resource != RLIMIT_STACK) exit(4);
  rl->rlim_cur = limit; rl->rlim_max = RLIM_INFINITY;
  return 0;
}
static long probe_sysconf(int name) { return name == _SC_PAGESIZE ? 4096 : -1; }
static int probe_getattr(pthread_t thread, pthread_attr_t *attr) {
  (void)thread; (void)attr; got++;
  return getattr_error;
}
static int probe_getstack(const pthread_attr_t *attr, void **addr, size_t *size) {
  (void)attr;
  if (getstack_error) return getstack_error;
  *addr = (void *)mock_lo; *size = mock_size;
  return 0;
}
static int probe_destroy(pthread_attr_t *attr) { (void)attr; destroyed++; return 0; }
#define getauxval probe_getauxval
#define getrlimit probe_getrlimit
#define sysconf probe_sysconf
#define pthread_getattr_np probe_getattr
#define pthread_attr_getstack probe_getstack
#define pthread_attr_destroy probe_destroy
"""
SUFFIX = r"""
static _Alignas(4096) char page[2 * 4096];
static void check(const char *what, uintptr_t here, uintptr_t expected, int pthread_calls, int destroys) {
  got = destroyed = 0;
  pys_recursion_state[2] = -1;
  stack_floor_at(here);
  if ((uintptr_t)pys_recursion_state[2] != expected || got != pthread_calls || destroyed != destroys) {
    fprintf(stderr, "incorrect stack floor (%s): %#llx, expected %#llx (%d pthread calls)\n", what,
            (unsigned long long)pys_recursion_state[2], (unsigned long long)expected, got);
    exit(1);
  }
}
int main(void) {
  uintptr_t KiB = 1024, MiB = 1024 * KiB;
  /* the main thread's mapping ends where exec's copy of the file name and a word end: end */
  char *name = page + 4096 - sizeof(void *) - 5;
  strcpy(name, "prog");
  uintptr_t end = (uintptr_t)page + 4096, here = end - 64 * KiB;
  execfn = name; limit = 8 * MiB;
  mock_lo = 0x100000; mock_size = 8 * MiB;   /* (pthread bounds the main thread's path must not use) */
  check("the main thread's 8 MiB: the full margin", here, end - 8 * MiB + 256 * KiB, 0, 0);
  limit = 1024 * MiB;
  check("the main thread's 1 GiB", here, end - 1024 * MiB + 256 * KiB, 0, 0);
  limit = 1001 * KiB;   /* (page-aligned up: 250 pages, of which an eighth) */
  check("the main thread's 1001 KiB: an eighth", here, end - 1000 * KiB + 125 * KiB, 0, 0);
  limit = 8 * MiB;
  check("a main thread frame within the margin: no floor", end - 8 * MiB + 100 * KiB, 0, 0, 0);
  /* otherwise the thread's pthread bounds */
  mock_lo = here - 4 * MiB; mock_size = 8 * MiB;
  limit = RLIM_INFINITY;
  check("an unlimited stack: the pthread bounds", here, here - 4 * MiB + 256 * KiB, 1, 1);
  limit = 8 * MiB;
  execfn = page + 100;   /* (ld.so ./prog: AT_EXECFN is an argument, no page boundary after it) */
  strcpy(page + 100, "./prog");
  check("AT_EXECFN not at a mapping's end: the pthread bounds", here, here - 4 * MiB + 256 * KiB, 1, 1);
  execfn = 0;
  check("no AT_EXECFN: the pthread bounds", here, here - 4 * MiB + 256 * KiB, 1, 1);
  execfn = name;
  uintptr_t thread = end - 64 * MiB;   /* (another thread's frame, outside the main thread's limit) */
  mock_lo = thread - 4 * MiB;
  check("another thread: its pthread bounds", thread, thread - 4 * MiB + 256 * KiB, 1, 1);
  mock_lo = thread - 256 * KiB; mock_size = 512 * KiB;
  check("a 512 KiB thread stack: an eighth of it", thread, thread - 256 * KiB + 64 * KiB, 1, 1);
  mock_lo = thread - 16 * MiB; mock_size = 8 * MiB;
  check("bounds below the frame (a switched stack): no floor", thread, 0, 1, 1);
  mock_lo = thread + MiB;
  check("bounds above the frame: no floor", thread, 0, 1, 1);
  mock_lo = thread - 100 * KiB;
  check("a frame already within the margin: no floor", thread, 0, 1, 1);
  mock_lo = thread - 4 * MiB; getattr_error = 1;
  check("no thread attributes: no floor", thread, 0, 1, 0);
  getattr_error = 0; getstack_error = 1;
  check("no stack in them: no floor", thread, 0, 1, 1);
  /* stack_floor itself: this frame's own bounds */
  uintptr_t frame = (uintptr_t)__builtin_frame_address(0);
  execfn = 0; getstack_error = 0; mock_lo = frame - 4 * MiB; mock_size = 8 * MiB;
  got = destroyed = 0;
  stack_floor();
  if ((uintptr_t)pys_recursion_state[2] != frame - 4 * MiB + 256 * KiB || got != 1) {
    fprintf(stderr, "incorrect stack floor (this frame): %#llx\n", (unsigned long long)pys_recursion_state[2]);
    exit(1);
  }
  puts("stack floor policy passed");
  return 0;
}
"""
# The issue's program (#1015): the work after the recursive call keeps every frame on the stack.
# "gen" nests generators instead, each level resuming the next (a counted resume's entry).
PROGRAM = '''import sys
from collections.abc import Iterator


def depth(n: int, out: list[int]) -> int:
    if n == 0:
        return 0
    r = depth(n - 1, out)
    out.append(r)
    return r + 1


def nest(n: int) -> Iterator[int]:
    if n == 0:
        yield 0
        return
    for v in nest(n - 1):
        yield v + 1


sys.setrecursionlimit(2000000)
out: list[int] = []
try:
    if sys.argv[1] == "gen":
        print(sum(nest(int(sys.argv[2]))))
    else:
        print(depth(int(sys.argv[2]), out), len(out))
except RecursionError as error:
    print("caught recursion:", error)
finally:
    print("finally")
'''
# A program without try or with: the runtime reports the error and exits at once.
BARE = '''import sys


def depth(n: int, out: list[int]) -> int:
    if n == 0:
        return 0
    r = depth(n - 1, out)
    out.append(r)
    return r + 1


sys.setrecursionlimit(2000000)
out: list[int] = []
print("output before the recursion is kept")
print(depth(int(sys.argv[1]), out), len(out))
'''
CAUGHT = f"caught recursion: {STACK_ERROR.split(': ', 1)[1]}\nfinally\n"


def floor_source():
    source = (ROOT / "runtime.c").read_text()
    match = re.search(r"^#if defined\(__has_feature\)\n.*?^static void stack_floor\(void\) \{[^\n]*\}\n", source, re.M | re.S)
    if match is None:
        raise AssertionError("runtime.c's stack_floor is missing")
    return match[0]


def limited(stack_kib):
    # the child's fixed stack limit (the one exec gives the program's main thread; None: unlimited),
    # and no core files
    def apply():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        size = resource.RLIM_INFINITY if stack_kib is None else stack_kib * KIB
        resource.setrlimit(resource.RLIMIT_STACK, (size, resource.getrlimit(resource.RLIMIT_STACK)[1]))
    return apply


def interpreter(executable):
    # the dynamic loader an ELF executable names (PT_INTERP), which can run it as a program
    data = Path(executable).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    phoff = int.from_bytes(data[0x20:0x28], "little")
    size, count = int.from_bytes(data[0x36:0x38], "little"), int.from_bytes(data[0x38:0x3a], "little")
    for at in range(phoff, phoff + size * count, size):
        if int.from_bytes(data[at:at + 4], "little") == 3:
            offset = int.from_bytes(data[at + 8:at + 16], "little")
            length = int.from_bytes(data[at + 32:at + 40], "little")
            return data[offset:offset + length].rstrip(b"\0").decode()
    return None


class StackFloorPolicyTests(unittest.TestCase):
    @unittest.skipUnless(CLANG and GLIBC, "clang and glibc are required for simulated stack bounds")
    def test_floor_follows_the_thread_bounds(self):
        self.check_native(floor_source(), 0)

    @unittest.skipUnless(CLANG and GLIBC, "clang and glibc are required for simulated stack bounds")
    def test_mutations_are_detected(self):
        source = floor_source()
        mutations = {
            "bounds that exclude the frame": ("lo && lo + margin < here && here <= hi ?", "lo && here ?"),
            "a margin larger than a small stack": ("(hi - lo) / 8 < STACK_MARGIN ? (hi - lo) / 8 : STACK_MARGIN", "STACK_MARGIN"),
            "a pthread failure ignored": ("if (!lo && !pthread_getattr_np(pthread_self(), &attr)) {",
                                          "if (!lo && (pthread_getattr_np(pthread_self(), &attr), 1)) {"),
            "AT_EXECFN not at a page boundary": ("if (end && page && !(end & (page - 1)) && here < end", "if (end && page && here < end"),
            "a frame outside the main thread's limit": (" && end - here < rl.rlim_cur) {", ") {"),
            "an unlimited stack": ("rl.rlim_cur < end - page && ", ""),
        }
        for name, (original, mutated) in mutations.items():
            with self.subTest(name):
                self.assertIn(original, source)
                self.check_native(source.replace(original, mutated), 1)

    def check_native(self, source, expected):
        with tempfile.TemporaryDirectory(prefix="pystachy-stack-floor-") as directory:
            executable = Path(directory) / "floor"
            result = subprocess.run([CLANG, "-O2", "-Wall", "-Wextra", "-Werror", "-x", "c", "-", "-o", str(executable)],
                                    input=PREFIX + source + SUFFIX, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 0:
                self.assertEqual(result.stdout, "stack floor policy passed\n")
            else:
                self.assertIn("incorrect stack floor", result.stderr)


@unittest.skipUnless(HAVE_LLVM and sys.platform.startswith("linux"), "complete LLVM on Linux is required for live JIT/AOT runs")
class StackFloorProgramTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hard = resource.getrlimit(resource.RLIMIT_STACK)[1]
        if hard != resource.RLIM_INFINITY and hard < 8 * MIB:
            raise unittest.SkipTest("the hard stack limit is below 8 MiB")
        cls.directory = tempfile.TemporaryDirectory(prefix="pystachy-stack-floor-run-")
        cls.work = Path(cls.directory.name)
        cls.environment = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        cls.environment.update(PYSTACHY_LLVM=LLVM, PYSTACHY_CACHE=str(cls.work / "cache"), PYSTACHY_IRCHECK="1")
        cls.compiler = [sys.executable, str(ROOT / "pystachy.py")]
        for name, text in (("deep", PROGRAM), ("bare", BARE)):
            (cls.work / f"{name}.py").write_text(text)
            build = subprocess.run([*cls.compiler, "build", str(cls.work / f"{name}.py"), "-o", str(cls.work / name)],
                                   cwd=ROOT, capture_output=True, text=True, env=cls.environment, timeout=600)
            if build.returncode != 0 or build.stderr != "":
                raise AssertionError(f"pystachy build {name}.py failed: {build.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_limited(self, command, stack_kib=8192, **variables):
        environment = dict(self.environment, **variables)
        return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=environment,
                              preexec_fn=limited(stack_kib), timeout=300)

    def aot(self, name, *args, stack_kib=8192, **variables):
        return self.run_limited([str(self.work / name), *args], stack_kib, **variables)

    def jit(self, name, *args, **variables):
        return self.run_limited([*self.compiler, "run", str(self.work / f"{name}.py"), *args], **variables)

    def assert_caught(self, result):
        # no signal: the stack's floor raised RecursionError, which the program caught
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout, CAUGHT)

    def test_recursion_that_fits_matches_cpython(self):
        oracle = self.run_limited([sys.executable, str(self.work / "deep.py"), "depth", "100000"])
        self.assertEqual((oracle.returncode, oracle.stderr), (0, ""))
        self.assertEqual(oracle.stdout, "100000 100000\nfinally\n")
        for result in (self.aot("deep", "depth", "100000"), self.aot("deep", "depth", "100000", PYSTACHY_GC_STRESS="1"),
                       self.jit("deep", "depth", "100000")):
            self.assertEqual((result.returncode, result.stderr, result.stdout), (0, "", oracle.stdout))

    def test_recursion_deeper_than_the_stack_raises_in_aot(self):
        # (CPython completes both: the documented deviation)
        for n in ("400000", "1000000"):
            self.assert_caught(self.aot("deep", "depth", n))
        self.assert_caught(self.aot("deep", "depth", "1000000", PYSTACHY_GC_STRESS="1"))

    def test_recursion_deeper_than_the_stack_raises_in_jit(self):
        self.assert_caught(self.jit("deep", "depth", "1000000"))
        self.assert_caught(self.jit("deep", "depth", "1000000", PYSTACHY_GC_STRESS_PROGRAM="1"))

    def test_generator_resumes_check_the_floor(self):
        oracle = self.run_limited([sys.executable, str(self.work / "deep.py"), "gen", "100"])
        self.assertEqual((oracle.returncode, oracle.stderr, oracle.stdout), (0, "", "100\nfinally\n"))
        small = self.aot("deep", "gen", "100")
        self.assertEqual((small.returncode, small.stderr, small.stdout), (0, "", oracle.stdout))
        self.assert_caught(self.aot("deep", "gen", "1000000"))
        self.assert_caught(self.jit("deep", "gen", "1000000"))

    def test_the_floor_follows_the_stack_limit(self):
        # 100,000 frames fit in 8 MiB, not in 1 MiB, whose floor is an eighth of the way up; 1,000,000
        # fit in 128 MiB (at up to 133 bytes a frame), which the floor leaves to the program
        self.assert_caught(self.aot("deep", "depth", "100000", stack_kib=1024))
        result = self.aot("deep", "depth", "1000000", stack_kib=131072)
        self.assertEqual((result.returncode, result.stderr, result.stdout), (0, "", "1000000 1000000\nfinally\n"))
        if resource.getrlimit(resource.RLIMIT_STACK)[1] == resource.RLIM_INFINITY:
            # (an unlimited stack reaches the mapping below it: no floor in practice)
            result = self.aot("deep", "depth", "1000000", stack_kib=None)
            self.assertEqual((result.returncode, result.stderr, result.stdout), (0, "", "1000000 1000000\nfinally\n"))

    def test_a_loader_run_as_a_program_finds_the_bounds_too(self):
        # (ld.so ./program points AT_EXECFN at its argument: the runtime asks pthread_getattr_np)
        loader = interpreter(self.work / "deep")
        if loader is None or not Path(loader).exists():
            self.skipTest("the executable names no dynamic loader")
        self.assert_caught(self.run_limited([loader, str(self.work / "deep"), "depth", "1000000"], 8192))

    def test_uncaught_error_ends_the_program_after_its_output(self):
        for result in (self.aot("bare", "1000000"), self.jit("bare", "1000000")):
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout, "output before the recursion is kept\n")
            self.assertEqual(result.stderr.splitlines()[-1:], [STACK_ERROR])


if __name__ == "__main__":
    unittest.main()
