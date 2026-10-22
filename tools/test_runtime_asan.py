"""Generated runtime ASan checks, including a deliberately uninstrumented control."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pystachy_compiler.driver import RTSO, address_runtime_ir, address_sanitized, llvm_dir

ROOT = Path(__file__).resolve().parents[1]
LLVM = llvm_dir()
CLANG = shutil.which(str(Path(LLVM) / "clang") if LLVM else "clang")
OPT = shutil.which(str(Path(LLVM) / "opt") if LLVM else "opt")
# Overridable by a local test runner using a nonstandard sanitizer runtime. CI
# uses Clang's standard runtime and fails if it cannot link or execute it.
LINK_FLAGS = []
RUN_ENV = {}

PROBE = r"""
extern void *malloc(unsigned long);
extern void free(void *);
typedef long long I;
typedef struct { I len, dict_hash, chars1; unsigned char s[]; } Str;
extern I pys_str_isascii(Str *);
int main(int argc, char **argv) {
    (void)argv;
    Str *s = malloc(sizeof(Str) + 1);
    if (!s) return 3;
    s->len = argc > 1 ? 2 : 1;
    s->dict_hash = 0;
    s->chars1 = 0;
    s->s[0] = 'a';
    /* The bad case advertises two bytes in a one-byte allocation: only the
       generated runtime function performs the invalid access. */
    volatile I result = pys_str_isascii(s);
    (void)result;
    free(s);
    return 0;
}
"""


def body(ir, name):
    match = re.search(r"^define[^\n]*@" + name + r"\([^\n]*\{\n(.*?)^}", ir, re.M | re.S)
    if match is None:
        raise AssertionError(f"missing runtime definition: {name}")
    return match[1]


class RuntimeASan(unittest.TestCase):
    def test_sanitizer_flag_order(self):
        cases = {
            "": False,
            "-fsanitize=undefined": False,
            "-fsanitize=kernel-address": False,
            "-fsanitize-recover=address": False,
            "-fsanitize=address": True,
            "-fsanitize=undefined,address": True,
            "-fsanitize=address -fno-sanitize=undefined": True,
            "-fsanitize=address -fno-sanitize=address": False,
            "-fsanitize=address -fno-sanitize=all": False,
            "-fsanitize=address -fno-sanitize=address,undefined": False,
            "-fno-sanitize=all -fsanitize=address": True,
        }
        for flags, expected in cases.items():
            with self.subTest(flags=flags):
                self.assertEqual(address_sanitized(flags.split()), expected)

    def test_marks_definitions_before_personality(self):
        ir = ("declare void @external()\n"
              "define internal i64 @helper(ptr %s) {\n  ret i64 0\n}\n"
              "define void @raises() cold noinline personality ptr @pys_personality {\n  unreachable\n}\n")
        marked = address_runtime_ir(ir)
        self.assertEqual(marked.count("sanitize_address"), 2)
        self.assertIn("@helper(ptr %s) sanitize_address {", marked)
        self.assertIn("@raises() sanitize_address cold noinline personality", marked)
        self.assertEqual(marked.replace(" sanitize_address", ""), ir)

    @unittest.skipUnless(CLANG and OPT, "LLVM is required for generated-runtime ASan controls")
    def test_cached_subset_instrumentation_and_overread_control(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "smoke.py"
            source.write_text('print("ascii".isascii())\nprint("hello".upper())\n')
            probe = tmp / "probe.c"
            probe.write_text(PROBE + RTSO)
            flags = ["-fsanitize=address", *LINK_FLAGS]
            env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_CFLAGS=" ".join(flags))
            for name in ("PYSTACHY_OPT", "PYSTACHY_PATH", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM"):
                env.pop(name, None)
            runenv = dict(env, ASAN_OPTIONS="detect_leaks=0:detect_stack_use_after_return=0", **RUN_ENV)
            checked = {}
            for instrument in (True, False):
                with self.subTest(instrument=instrument):
                    cache = tmp / ("instrumented" if instrument else "control")
                    cache.mkdir()
                    env["PYSTACHY_CACHE"] = str(cache)
                    executable = cache / "smoke"
                    # The negative control changes no repository files and has a
                    # private cache. Removing the attribute must defeat the probe.
                    script = ("import sys; from src.pystachy_compiler import driver; "
                              + ("" if instrument else "driver.address_runtime_ir = lambda ir: ir; ")
                              + "sys.argv = sys.argv[1:]; driver.main()")
                    build = subprocess.run([sys.executable, "-c", script, str(ROOT / "pystachy.py"),
                                            "build", str(source), "-o", str(executable)],
                                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                    self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                    bitcode = list(cache.glob("runtime-py-*.bc"))
                    self.assertEqual(len(bitcode), 1, str(list(cache.iterdir())))
                    ir = subprocess.run([OPT, "-S", "-passes=verify", str(bitcode[0]), "-o", "-"],
                                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(ir.returncode, 0, ir.stderr)
                    self.assertEqual("__asan_report_load" in body(ir.stdout, "pys_str_isascii"), instrument)
                    self.assertEqual("__asan_report_store" in body(ir.stdout, "pys_str_upper"), instrument)
                    for stress in ("", "1"):
                        good = subprocess.run([str(executable)], env=dict(runenv, PYSTACHY_GC_STRESS=stress),
                                              capture_output=True, text=True, timeout=30)
                        self.assertEqual((good.returncode, good.stdout, good.stderr), (0, "True\nHELLO\n", ""))
                    if sys.platform == "linux":
                        jitenv = dict(runenv, PYSTACHY_CACHE=str(cache))
                        if "LD_PRELOAD" not in RUN_ENV:
                            triple = subprocess.run([CLANG, "-dumpmachine"], capture_output=True,
                                                    text=True, check=True).stdout.strip()
                            soname = "libclang_rt.asan-" + triple.split("-")[0] + ".so"
                            library = subprocess.run([CLANG, "-print-file-name=" + soname], capture_output=True,
                                                     text=True, check=True).stdout.strip()
                            self.assertTrue(Path(library).is_file(), library)
                            jitenv["LD_PRELOAD"] = library
                        for stress in ("", "1"):
                            jit = subprocess.run([sys.executable, "-c", script, str(ROOT / "pystachy.py"),
                                                  "run", str(source)], cwd=ROOT,
                                                 env=dict(jitenv, PYSTACHY_GC_STRESS_PROGRAM=stress),
                                                 capture_output=True, text=True, timeout=90)
                            self.assertEqual((jit.returncode, jit.stdout, jit.stderr), (0, "True\nHELLO\n", ""))
                    # Compile the already-instrumented bitcode without sanitizer
                    # flags; only the final link adds the ASan runtime library.
                    obj = cache / "runtime.o"
                    result = subprocess.run([CLANG, "-O2", "-c", str(bitcode[0]), "-o", str(obj)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    native = cache / "probe"
                    probeobj = cache / "probe.o"
                    result = subprocess.run([CLANG, "-O2", "-c", str(probe), "-o", str(probeobj)],
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([CLANG, str(probeobj), str(obj), "-o", str(native), "-lm", *flags],
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    good = subprocess.run([str(native)], env=runenv, capture_output=True, text=True, timeout=30)
                    self.assertEqual((good.returncode, good.stderr), (0, ""))
                    bad = subprocess.run([str(native), "bad"], env=runenv, capture_output=True, text=True, timeout=30)
                    checked[instrument] = bad
            self.assertEqual(set(checked), {True, False})
            self.assertNotEqual(checked[True].returncode, 0)
            self.assertIn("AddressSanitizer: heap-buffer-overflow", checked[True].stderr)
            self.assertIn("READ of size", checked[True].stderr)
            self.assertEqual((checked[False].returncode, checked[False].stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()
