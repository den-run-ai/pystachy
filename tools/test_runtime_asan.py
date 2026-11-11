"""Generated-code ASan checks, including deliberately uninstrumented controls."""
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

# Independent test source: poison only the list's scalar backing storage. The
# loop's element load belongs to generated user code; it does not call a runtime
# accessor. Unpoison before printing/cleanup so the control cannot be detected
# later by a runtime access. This injects a deliberate invalid read, not a Python
# bounds-check failure or an assertion about arena-level GC poisoning.
USER_PROBE = '''\
from ffi import extern, export, c_size_t

@extern('', '__asan_poison_memory_region')
def _poison(values: list[float], size: c_size_t) -> None:
    ...

@extern('', '__asan_unpoison_memory_region')
def _unpoison(values: list[float], size: c_size_t) -> None:
    ...

def _probe(bad: bool) -> float:
    values = [12.5, 7.0]
    if bad:
        _poison(values, 8)
    total = 0.0
    for value in values:
        total += value
    _unpoison(values, 8)
    return total
'''


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

    @unittest.skipUnless(CLANG and OPT, "LLVM is required for generated-user ASan controls")
    def test_aot_user_load_and_extension_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / "user_probe.py"
            source.write_text(USER_PROBE + "\nimport sys\nprint(_probe(len(sys.argv) > 1))\n")
            extension = tmp / "user_ext.py"
            extension.write_text(USER_PROBE + "\n@export\ndef probe(bad: bool) -> float:\n    return _probe(bad)\n")
            flags = ["-fsanitize=address", *LINK_FLAGS]
            env = dict(os.environ, PYSTACHY_HOME=str(ROOT), PYSTACHY_CFLAGS=" ".join(flags),
                       PYSTACHY_CACHE=str(tmp / "cache"))
            for name in ("PYSTACHY_OPT", "PYSTACHY_PATH", "PYSTACHY_GC_STRESS", "PYSTACHY_GC_STRESS_PROGRAM",
                         "PYSTACHY_PROGRAM_CACHE", "PYSTACHY_DEBUG_LINES"):
                env.pop(name, None)
            runenv = dict(env, ASAN_OPTIONS="detect_leaks=0:detect_stack_use_after_return=0", **RUN_ENV)
            other = tmp / "other.c"
            other.write_text("volatile long other_global[1];\nlong other_read(void) { return other_global[0]; }\n")
            otherobj = tmp / "other.o"
            compiled = subprocess.run([CLANG, "-O2", "-c", str(other), "-o", str(otherobj), *flags],
                                      capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            checked = {}
            for instrument in (True, False):
                # Leave runtime instrumentation enabled in both variants. Only
                # omit the user module's attributes in the negative control.
                script = ("import shlex, shutil, sys; from src.pystachy_compiler import driver; "
                          + ("" if instrument else
                             "mark = driver.address_runtime_ir; "
                             "driver.address_runtime_ir = lambda ir: ir if '@f._probe(' in ir else mark(ir); ")
                          + "\ntimed = driver.timed_sh\n"
                          + "def retain_object(name, command):\n"
                          + "    if name == 'program.link':\n"
                          + "        shutil.copyfile(shlex.split(command)[1], sys.argv[sys.argv.index('-o') + 1] + '.o')\n"
                          + "    return timed(name, command)\n"
                          + "driver.timed_sh = retain_object\n"
                          + "sys.argv = sys.argv[1:]; driver.main()")
                for level in ("0", "2"):
                    with self.subTest(instrument=instrument, level=level):
                        executable = tmp / f"user-{instrument}-{level}"
                        retained = tmp / f"user-{instrument}-{level}.ll"
                        build = subprocess.run([sys.executable, "-c", script, str(ROOT / "pystachy.py"), "build",
                                                str(source), "-o", str(executable), "--emit-ir", str(retained)],
                                               cwd=ROOT, env=dict(env, PYSTACHY_AOT_OPT=level),
                                               capture_output=True, text=True, timeout=120)
                        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                        self.assertNotIn("sanitize_address", retained.read_text())
                        for stress in ("", "1"):
                            good = subprocess.run([str(executable)], env=dict(runenv, PYSTACHY_GC_STRESS=stress),
                                                  capture_output=True, text=True, timeout=30)
                            self.assertEqual((good.returncode, good.stdout, good.stderr), (0, "19.5\n", ""))
                        checked[instrument, "aot" + level] = subprocess.run([str(executable), "bad"], env=runenv,
                                                                          capture_output=True, text=True, timeout=30)
                        # The user module precedes the C runtime in llvm-link.
                        # Both modules' constructors must survive either native
                        # link order with another independently sanitized object.
                        for order in (0, 1):
                            obj = str(executable) + ".o"
                            objects = [str(otherobj), obj] if order == 0 else [obj, str(otherobj)]
                            linked = tmp / f"user-{instrument}-{level}-link{order}"
                            result = subprocess.run([CLANG, *objects, "-o", str(linked), "-lm", "-ldl", *flags],
                                                    capture_output=True, text=True, timeout=30)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            good = subprocess.run([str(linked)], env=runenv, capture_output=True, text=True, timeout=30)
                            self.assertEqual((good.returncode, good.stdout, good.stderr), (0, "19.5\n", ""))
                            checked[instrument, f"aot{level}-link{order}"] = subprocess.run(
                                [str(linked), "bad"], env=runenv, capture_output=True, text=True, timeout=30)
                if sys.platform == "linux":
                    module = tmp / "user_ext.abi3.so"
                    build = subprocess.run([sys.executable, "-c", script, str(ROOT / "pystachy.py"),
                                            "ext", str(extension), "-o", str(module)], cwd=ROOT, env=env,
                                           capture_output=True, text=True, timeout=120)
                    self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                    extenv = dict(runenv)
                    if "LD_PRELOAD" not in RUN_ENV:
                        triple = subprocess.run([CLANG, "-dumpmachine"], capture_output=True, text=True,
                                                check=True, timeout=30).stdout.strip()
                        soname = "libclang_rt.asan-" + triple.split("-")[0] + ".so"
                        library = subprocess.run([CLANG, "-print-file-name=" + soname], capture_output=True,
                                                 text=True, check=True, timeout=30).stdout.strip()
                        self.assertTrue(Path(library).is_file(), library)
                        extenv["LD_PRELOAD"] = library
                    for stress in ("", "1"):
                        good = subprocess.run([sys.executable, "-c", "import user_ext; print(user_ext.probe(False))"],
                                              cwd=tmp, env=dict(extenv, PYSTACHY_GC_STRESS=stress),
                                              capture_output=True, text=True, timeout=30)
                        self.assertEqual((good.returncode, good.stdout, good.stderr), (0, "19.5\n", ""))
                    checked[instrument, "extension"] = subprocess.run(
                        [sys.executable, "-c", "import user_ext; print(user_ext.probe(True))"],
                        cwd=tmp, env=extenv, capture_output=True, text=True, timeout=30)
            self.assertEqual(len(checked), 14 if sys.platform == "linux" else 12)
            for (instrument, tier), result in checked.items():
                with self.subTest(instrument=instrument, tier=tier):
                    if instrument:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("AddressSanitizer: use-after-poison", result.stderr)
                        self.assertIn("READ of size 8", result.stderr)
                    else:
                        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "19.5\n", ""))

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
                    build_command = [sys.executable, "-c", script, str(ROOT / "pystachy.py"),
                                     "build", str(source), "-o", str(executable)]
                    for attempt in range(2):
                        build = subprocess.run(build_command, cwd=ROOT, env=env,
                                               capture_output=True, text=True, timeout=120)
                        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
                        bitcode = list(cache.glob("runtime-py-*.bc"))
                        if bitcode:
                            break
                        # A just-edited compiler deliberately does not publish a
                        # cache entry until its sources are at least two seconds
                        # old. The first real build gives those inputs time to settle.
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
                                                    text=True, check=True, timeout=30).stdout.strip()
                            soname = "libclang_rt.asan-" + triple.split("-")[0] + ".so"
                            library = subprocess.run([CLANG, "-print-file-name=" + soname], capture_output=True,
                                                     text=True, check=True, timeout=30).stdout.strip()
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
                    for external_asan in (False, True):
                        probeobj = cache / ("external-asan.o" if external_asan else "probe.o")
                        result = subprocess.run([CLANG, "-O2", "-c", str(probe), "-o", str(probeobj)]
                                                + (["-fsanitize=address"] if external_asan else []),
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        # LLVM linking two sanitized modules must not leave a
                        # renamed constructor in C's COMDAT group. Another ASan
                        # object can win that group in either native link order.
                        for order in (0, 1):
                            native = cache / f"probe-{external_asan}-{order}"
                            objects = [str(probeobj), str(obj)] if order == 0 else [str(obj), str(probeobj)]
                            result = subprocess.run([CLANG, *objects, "-o", str(native), "-lm", *flags],
                                                    capture_output=True, text=True, timeout=30)
                            self.assertEqual(result.returncode, 0, result.stderr)
                            good = subprocess.run([str(native)], env=runenv, capture_output=True, text=True, timeout=30)
                            self.assertEqual((good.returncode, good.stderr), (0, ""))
                            bad = subprocess.run([str(native), "bad"], env=runenv, capture_output=True, text=True, timeout=30)
                            checked[instrument, external_asan, order] = bad
            self.assertEqual(len(checked), 8)
            for (instrument, external_asan, order), result in checked.items():
                with self.subTest(instrument=instrument, external_asan=external_asan, order=order):
                    if instrument:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("AddressSanitizer: heap-buffer-overflow", result.stderr)
                        self.assertIn("READ of size", result.stderr)
                    else:
                        self.assertEqual((result.returncode, result.stderr), (0, ""))



if __name__ == "__main__":
    unittest.main()
