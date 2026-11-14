"""Masked int expressions that fit in 32 bits are computed as 32-bit values (gen_low32).

Runs the hosted compiler's `ir` command: no LLVM is needed. The values are checked against
CPython by tests/programs/numbers/int_masked_low32.py; this pins which expressions take the
32-bit path, and how a rotation is written there.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''MASK = 0xFFFFFFFF
WIDE = 0x100000000


def helper(x: int) -> int:
    return x + 1


def rotation(x: int) -> int:
    return ((x << 5) | (x >> 27)) & 0xFFFFFFFF


def rotation_right_named_mask(x: int) -> int:
    return MASK & ((x >> 2) | (x << 30))


def sum_of_rotations(x: int, y: int) -> int:
    return ((((x << 7) | (x >> 25)) ^ ((y >> 13) | (y << 19)) ^ (x >> 3)) + y * 3 - 1) & MASK


def small_mask(x: int, y: int) -> int:
    return (x + y) & 0xFF


def wide_mask(x: int) -> int:
    return ((x << 5) | (x >> 27)) & WIDE


def literal_wide_mask(x: int, y: int) -> int:
    return (x + y) & 0x1FFFFFFFF


def variable_mask(x: int, y: int) -> int:
    return (x + 1) & y


def call_operand(x: int) -> int:
    return (helper(x) + 1) & 0xFF


def long_shift(x: int) -> int:
    return (x << 32) & MASK


def variable_count(x: int, c: int) -> int:
    return ((x << c) | (x >> (32 - c))) & MASK


def float_operand(x: int, flag: bool) -> int:
    return (x + flag) & MASK


def many(x: int) -> int:
    return (BODY) & MASK


print(rotation(1), rotation_right_named_mask(1), sum_of_rotations(1, 2), small_mask(1, 2), wide_mask(1),
      literal_wide_mask(1, 2), variable_mask(1, 2), call_operand(1), long_shift(1), variable_count(1, 2),
      float_operand(1, True), many(1))
'''


def functions(ir):
    found = {}
    for match in re.finditer(r"^define [^\n]*@f\.(\w+)\([^\n]*\n(.*?)^}", ir, re.M | re.S):
        found[match.group(1)] = match.group(2)
    return found


class MaskedLow32(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "probe.py"
            # (more nodes than the test for the 32-bit path looks at: the 64-bit steps, in linear time)
            source.write_text(PROGRAM.replace("BODY", " + ".join(["x"] * 400)))
            env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
            env.update(PYSTACHY_HOME=str(ROOT), PYSTACHY_CACHE=str(Path(temporary) / "cache"))
            result = subprocess.run([sys.executable, str(ROOT / "pystachy.py"), "ir", str(source)], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        cls.fns = functions(result.stdout)

    def narrow(self, name):
        return re.findall(r"= (\w+) i32 ", self.fns[name])

    def test_a_rotation_is_two_shifts_of_32_bit_values(self):
        # (truncated: x's low bits and the shifted x; a mask that is a module's constant is read.
        # LLVM makes these a rotation where it knows x to be below 2**32)
        for name, truncated in (("rotation", 2), ("rotation_right_named_mask", 3)):
            with self.subTest(name=name):
                body = self.fns[name]
                self.assertEqual(sorted(self.narrow(name)), ["and", "or", "shl", "zext"])
                self.assertEqual(len(re.findall(r"= trunc i64 ", body)), truncated)
                self.assertEqual(len(re.findall(r"= ashr i64 ", body)), 1)
                self.assertNotIn("= shl i64", body)
                self.assertNotIn("with.overflow", body)

    def test_a_tree_of_ints_under_a_32_bit_mask_is_narrow(self):
        ops = self.narrow("sum_of_rotations")
        self.assertEqual(ops.count("shl"), 2)
        self.assertEqual(len(re.findall(r"= ashr i64 ", self.fns["sum_of_rotations"])), 3)
        self.assertEqual(ops.count("mul"), 1)
        self.assertEqual(ops.count("sub"), 1)
        self.assertEqual(ops.count("zext"), 1)
        self.assertNotIn("with.overflow", self.fns["sum_of_rotations"])
        self.assertEqual(sorted(self.narrow("small_mask")), ["add", "and", "zext"])

    def test_other_expressions_keep_the_64_bit_steps(self):
        for name in ("wide_mask", "literal_wide_mask", "variable_mask", "call_operand", "long_shift", "variable_count",
                     "float_operand", "many"):
            with self.subTest(name=name):
                self.assertEqual(self.narrow(name), [])
                self.assertNotIn("zext i32", self.fns[name])


if __name__ == "__main__":
    unittest.main()
