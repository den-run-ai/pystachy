"""UBSan's compiler builtins survive the driver's shared and object JIT paths."""
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pystachy_compiler.driver import llvm_dir

ROOT = Path(__file__).resolve().parents[1]
LLVM = llvm_dir()
CLANG = shutil.which(str(Path(LLVM) / "clang") if LLVM else "clang")
LLI = shutil.which(str(Path(LLVM) / "lli") if LLVM else "lli")

# AArch64 lowers UBSan's checked i128 multiply to this builtin; x86 can inline
# that check. Calling it explicitly makes the missing-library control meaningful
# on either architecture, without depending on the optimizer's lowering choice.
RUNTIME = """extern __int128 __muloti4(__int128, __int128, int *);
int wide_mul(int factor) {
    int overflow = 0;
    __int128 result = __muloti4((__int128)1 << 126, factor, &overflow);
    (void)result;
    return overflow;
}
long long checked_add(long long a, long long b) { return a + b; }
"""
PROGRAM = """#include <limits.h>
#include <stdio.h>
extern int wide_mul(int);
extern long long checked_add(long long, long long);
long long pys_obj_eq(long long c, long long a, long long b) { return 0; }
long long pys_obj_cmp(long long c, long long op, long long a, long long b) { return 0; }
void *pys_obj_repr(long long c, long long a, long long b) { return 0; }
int main(int argc, char **argv) {
    if (argc > 1) return (int)checked_add(LLONG_MAX, 1);
    if (wide_mul(1) != 0 || wide_mul(2) != 1 || checked_add(20, 22) != 42) return 2;
    puts("wide builtin and UBSan: ok");
    return 0;
}
"""
# Only the front end is replaced with tiny valid modules. The real driver still
# compiles, caches, links and loads its runtime through the actual LLVM tools.
DRIVER = """import os, sys
from pathlib import Path
from src.pystachy_compiler import driver
driver.compile_program = lambda *args: Path(os.environ['PROBE_IR']).read_text()
driver.runtime_ir = lambda *args: '; empty subset runtime\\n'
driver.RTPARTS = ['probe/empty.h']
sys.argv = sys.argv[1:]
driver.main()
"""


@unittest.skipUnless(sys.platform == "linux" and CLANG and LLI, "Linux LLVM is required for UBSan JIT controls")
class RuntimeUBSan(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pystachy ubsan ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        (self.home / "runtime.c").write_text(RUNTIME)
        (self.home / "runtime.py").write_text("# empty subset runtime\n")
        (self.home / "probe").mkdir()
        (self.home / "probe/empty.h").write_text("/* fixture include */\n")
        self.source = self.root / "program.py"
        self.source.write_text("# the entry module is supplied by PROBE_IR\n")
        source = self.root / "program.c"
        source.write_text(PROGRAM)
        self.ir = self.root / "program.ll"
        result = subprocess.run([CLANG, "-O1", "-S", "-emit-llvm", str(source), "-o", str(self.ir)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.ir.write_text("\n".join(line for line in self.ir.read_text().splitlines()
                                     if not line.startswith("target ")) + "\n")
        match = re.search(r'^UBSAN="([^"]+)"$', (ROOT / "tests/verify.sh").read_text(), re.M)
        self.assertIsNotNone(match, "verification's UBSan configuration is missing")
        self.flags = shlex.split(match[1])
        triple = subprocess.run([CLANG, "-dumpmachine"], capture_output=True, text=True,
                                check=True, timeout=30).stdout.strip()
        soname = "libclang_rt.ubsan_standalone-" + triple.split("-")[0] + ".so"
        library = subprocess.run([CLANG, "-print-file-name=" + soname], capture_output=True, text=True,
                                 check=True, timeout=30).stdout.strip()
        self.assertTrue(Path(library).is_file(), "install libclang-rt-18-dev: " + library)
        self.tools = self.root / "llvm"
        self.tools.mkdir()
        for tool in ("clang", "llvm-as", "llvm-link", "opt", "lli"):
            real = shutil.which(str(Path(LLVM) / tool) if LLVM else tool)
            self.assertIsNotNone(real, tool)
            wrapper = self.tools / tool
            # Force the real driver's existing object fallback without depending
            # on whether this test user can mount a noexec cache filesystem.
            script = f"#!{sys.executable}\nimport json, os, sys\nargs = sys.argv[1:]\n"
            if tool == "clang":
                script += "if '-shared' in args and os.environ.get('PROBE_OBJECT'): sys.exit(1)\n"
            if tool == "lli":
                script += ("with open(os.environ['PROBE_ARGS'], 'w') as stream: json.dump(args, stream)\n"
                           "if os.environ.get('PROBE_DROP_ARCHIVE'):\n"
                           "    args = [a for a in args if not a.startswith('-extra-archive=')]\n")
            script += f"os.execv({real!r}, [{real!r}, *args])\n"
            wrapper.write_text(script)
            wrapper.chmod(0o755)
        self.args = self.root / "lli.json"
        self.env = dict(os.environ, PYSTACHY_HOME=str(self.home), PYSTACHY_LLVM=str(self.tools),
                        PYSTACHY_CACHE=str(self.root / "cache"), PROBE_IR=str(self.ir), PROBE_ARGS=str(self.args),
                        LD_PRELOAD=library, UBSAN_OPTIONS="handle_segv=0")
        for name in ("PYSTACHY_OPT", "PYSTACHY_PATH", "PYSTACHY_GC", "PYSTACHY_GC_STRESS",
                     "PYSTACHY_GC_STRESS_PROGRAM", "PYSTACHY_JIT_CODEGEN", "PYSTACHY_JIT_INLINE"):
            self.env.pop(name, None)

    def run_probe(self, mode, *, overflow=False, flags=None, drop_archive=False):
        env = dict(self.env, PYSTACHY_CFLAGS=" ".join(self.flags if flags is None else flags),
                   PROBE_OBJECT="1" if mode == "object" else "", PROBE_DROP_ARCHIVE="1" if drop_archive else "",
                   PYSTACHY_CACHE=str(self.root / ("cache-" + mode)))
        return subprocess.run([sys.executable, "-c", DRIVER, str(ROOT / "pystachy.py"), "run", str(self.source)]
                              + (["overflow"] if overflow else []), cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=60)

    def test_shared_and_object_paths_resolve_builtins_and_keep_ubsan(self):
        for mode in ("shared", "object"):
            with self.subTest(mode=mode):
                good = self.run_probe(mode)
                self.assertEqual((good.returncode, good.stdout, good.stderr),
                                 (0, "wide builtin and UBSan: ok\n", ""))
                args = json.loads(self.args.read_text())
                self.assertIn("-dlopen=/dev/fd/8" if mode == "shared" else "-extra-object=/dev/fd/8", args)
                if mode == "object":
                    self.assertEqual(len([a for a in args if a.startswith("-extra-archive=")]), 1)
                bad = self.run_probe(mode, overflow=True)
                self.assertNotEqual(bad.returncode, 0)
                self.assertIn("runtime error: signed integer overflow", bad.stderr)
                self.assertNotIn("__muloti4", bad.stderr)

    def test_missing_builtins_fail_for_shared_and_object_paths(self):
        # Restore the old shared-library link, then the old bare-object loading
        # behavior. Both must fail for the missing builtin, not an unrelated error.
        flags = [flag for flag in self.flags if not flag.startswith(("--rtlib=", "-rtlib="))]
        old_shared = self.run_probe("shared", flags=[*flags, "--rtlib=libgcc"])
        old_object = self.run_probe("object", drop_archive=True)
        for mode, result in (("shared", old_shared), ("object", old_object)):
            with self.subTest(mode=mode):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("__muloti4", result.stderr)


if __name__ == "__main__":
    unittest.main()
