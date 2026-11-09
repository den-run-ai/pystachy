"""Emitted LLVM that every release from 18 to 23 reads alike.

Float constants: LLVM 23 deprecates the hexadecimal double form (0x and 16 digits), which its
successor removes, and LLVM 18 to 22 cannot read the f0x form that replaces it. fbits() spells a
finite double as its shortest decimal and an infinity or a NaN as a bitcast of its bits.

coro.end: LLVM 22 made llvm.coro.end return void and rejects the three-argument declaration
returning i1 that LLVM 18 to 21 define. Generators call the older two-argument form, unnamed,
which each release upgrades to its own signature as it reads it.

The text checks need no LLVM; with the driver's toolchain (PYSTACHY_LLVM, else its discovery),
opt must also read each float spelling back as the same bits and lower a generator, and the
driver's late passes must inline the allocator's fast path, which LLVM 23's forceattrs changed.
"""
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.pystachy_compiler import driver
from src.pystachy_compiler.utils import fbits, fconst, float_slot


ROOT = Path(__file__).resolve().parents[1]
TEXTS = ["0.0", "-0.0", "1.0", "0.1", "-1.5", "1e-09", "1e+16", "1e22", "1e23", "123.0",
         "3.141592653589793", "5e-324", "-5e-324", "2.225073858507201e-308",
         "2.2250738585072014e-308", "1.7976931348623157e+308", "9223372036854775808.0",
         "-9223372036854775808.0", "1e309", "-1e309", "inf", "-inf", "nan"]
# a hexadecimal double (not part of a name or a string's text) or LLVM 23's f0x form
HEXFLOAT = re.compile(r"(?<![\w.$\"-])f?0x[0-9A-Fa-f]{16}(?![\w.])")
# the allocator's fast path, out of line, as runtime.c's pys_new reaches AOT's late step (noinline, and
# optnone too from a runtime compiled at -O0) and as the JIT tier's JITFAST copies do
ALLOCATOR = """@pys_fl = external global [80 x ptr]
declare ptr @pys_gc_slow(i64, i64)
define internal ptr @{name}(i64 %n) {attributes} {{
  %s = icmp ult i64 %n, 136
  br i1 %s, label %f, label %w
f:
  %h = getelementptr ptr, ptr @pys_fl, i64 %n
  %p = load ptr, ptr %h
  %z = icmp eq ptr %p, null
  br i1 %z, label %w, label %o
o:
  ret ptr %p
w:
  %r = call ptr @pys_gc_slow(i64 %n, i64 0)
  ret ptr %r
}}
define ptr @user() {{
  %p = call ptr @{name}(i64 56)
  ret ptr %p
}}
"""
GENERATOR = ("def count(n: int):\n"
             "    i = 0\n"
             "    while i < n:\n"
             "        yield i\n"
             "        i += 1\n"
             "for k in count(3):\n"
             "    print(k)\n")


def expected(text):
    # the bits as a signed i64: CPython's double, and every NaN float("nan")'s 0x7FF8000000000000
    value = float(text)
    raw = 0x7FF8000000000000 if math.isnan(value) else struct.unpack("<Q", struct.pack("<d", value))[0]
    return raw - (1 << 64) if raw >= 1 << 63 else raw


def compile_source(name, source):
    with patch.dict("os.environ", {"PYSTACHY_IRCHECK": "1"}):
        return driver.compile_program(name, source, [str(ROOT / "lib")], "")


def llvm_tool(name):
    directory = driver.llvm_dir()
    path = os.path.join(directory, name) if directory else shutil.which(name)
    return path if path and os.access(path, os.X_OK) else None


def opt(module_text, passes, options=()):
    with tempfile.TemporaryDirectory() as scratch:
        module = Path(scratch) / "module.ll"
        module.write_text(module_text)
        return subprocess.run([llvm_tool("opt"), "-S", "-passes=" + passes, *options, str(module), "-o", "-"],
                              capture_output=True, text=True, timeout=120)


class FloatSpellingTests(unittest.TestCase):
    def test_spellings_keep_exact_bits(self):
        for text in TEXTS:
            with self.subTest(text=text):
                spelled = fbits(text)
                self.assertIsNone(HEXFLOAT.search(spelled))
                self.assertTrue(fconst(spelled))
                self.assertEqual(int(float_slot(spelled)), expected(text))
                value = float(text)
                if math.isfinite(value):
                    # LLVM's decimal syntax needs the point: 1e-09 is 1.0e-09
                    self.assertRegex(spelled, r"^-?[0-9]+\.[0-9]+(e[-+][0-9]+)?$")
                    self.assertEqual(struct.pack("<d", float(spelled)), struct.pack("<d", value))
                else:
                    self.assertEqual(spelled, f"bitcast (i64 {expected(text)} to double)")

    def test_values_computed_at_run_time_are_not_constants(self):
        for value in ["%t1", "%x.3", "@g", "@dbf.m$1", "", "-", "undef", "null", "true"]:
            with self.subTest(value=value):
                self.assertFalse(fconst(value))

    def test_program_ir_has_no_hexadecimal_doubles(self):
        source = ("import math\n"
                  "def scale(x: float) -> float:\n"
                  "    return x * 2.5 + 1e-09 - 5e-324\n"
                  "values = [" + ", ".join(f"float('{t}')" if t in ["inf", "-inf", "nan"] else t
                                           for t in TEXTS) + "]\n"
                  "constants = [" + ", ".join(["-0.0", "1e309", "-1e309", "5e-324"] * 8) + "]\n"
                  "pair = (0.5, -0.0, 1e309)\n"
                  "print(scale(3.0), math.nan, math.inf, math.pi, values, constants, pair)\n"
                  "print(math.isclose(1.0, 1.0 + 1e-12), int(2.0 ** 62), 7 == 7.0)\n")
        ir = compile_source("float_constants_probe.py", source)
        self.assertIsNone(HEXFLOAT.search(ir))
        self.assertIn("2.5", ir)
        self.assertIn(f"bitcast (i64 {expected('nan')} to double)", ir)


class CoroEndTests(unittest.TestCase):
    def test_generators_call_the_two_argument_form(self):
        ir = compile_source("coro_end_probe.py", GENERATOR)
        self.assertIn("presplitcoroutine", ir)
        lines = re.findall(r"^.*@llvm\.coro\.end\b.*$", ir, re.M)
        self.assertIn("declare i1 @llvm.coro.end(ptr, i1)", lines)
        calls = [line for line in lines if not line.startswith("declare ")]
        self.assertTrue(calls)
        self.assertEqual(set(calls), {"  call i1 @llvm.coro.end(ptr %coro.hdl, i1 false)"})


@unittest.skipUnless(llvm_tool("opt"), "LLVM's opt is not installed")
class LlvmReadsItTests(unittest.TestCase):
    def test_opt_folds_each_float_spelling_to_its_bits(self):
        lines = [f"@g{i} = constant i64 bitcast (double {fbits(t)} to i64)" for i, t in enumerate(TEXTS)]
        # and as operands of instructions, as the compiler places them
        lines += ["define double @use(double %x, i1 %c) {", "entry:"]
        for i, t in enumerate(TEXTS):
            lines += [f"  %a{i} = fadd double %x, {fbits(t)}",
                      f"  %b{i} = select i1 %c, double {fbits(t)}, double %a{i}",
                      f"  %k{i} = fcmp olt double %b{i}, {fbits(t)}"]
        lines += [f"  ret double %b{len(TEXTS) - 1}", "}"]
        run = opt("\n".join(lines) + "\n", "verify")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, "")
        folded = dict(re.findall(r"^@g([0-9]+) = constant i64 (-?[0-9]+)$", run.stdout, re.M))
        self.assertEqual([int(folded[str(i)]) if str(i) in folded else None for i in range(len(TEXTS))],
                         [expected(t) for t in TEXTS])

    def test_opt_upgrades_coro_end_and_lowers_the_generator(self):
        ir = compile_source("coro_end_probe.py", GENERATOR)
        run = opt(ir, "coro-early,cgscc(coro-split),coro-cleanup")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stderr, "")
        # read as the release's own three-argument intrinsic (returning i1 or void), then lowered
        declared = re.findall(r"^declare (\w+) @llvm\.coro\.end\((.*)\)", run.stdout, re.M)
        self.assertIn(declared, [[("i1", "ptr, i1, token")], [("void", "ptr, i1, token")]])
        self.assertIsNone(re.search(r"call .*@llvm\.coro\.end\(", run.stdout))
        self.assertIn("presplitcoroutine", ir)
        self.assertNotIn("presplitcoroutine", run.stdout)

    def test_late_passes_inline_the_allocator_fast_path(self):
        # LLVM 23's forceattrs adds before it removes and refuses alwaysinline beside noinline or
        # optnone: the driver's LATE_PASSES run it twice, and LATE_INLINE removes optnone first
        for name, attributes, options in [("pys_new", "noinline", driver.LATE_INLINE),
                                          ("pys_new", "noinline optnone", driver.LATE_INLINE),
                                          ("pys_new", "noinline", driver.JITLATE),
                                          ("pys_alloc", "noinline", driver.JITLATE)]:
            with self.subTest(name=name, attributes=attributes, options=options):
                module = ALLOCATOR.format(name=name, attributes=attributes)
                run = opt(module, driver.LATE_PASSES, options.split())
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertNotIn(f"call ptr @{name}(", run.stdout)
                self.assertIn("call ptr @pys_gc_slow(i64 56, i64 0)", run.stdout)


if __name__ == "__main__":
    unittest.main()
