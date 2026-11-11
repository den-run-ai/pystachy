"""Check promoting ints' fit claims in real IR, and independently corrupt them."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_int
from check_lean_int import check_all, definitions, evaluate, known_claims, operands

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tools" / "lean_boundary" / ".lake" / "build" / "bin" / "pystachy-int"
if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean promoting-int checker is required; build tools/lean_boundary first")

# Each operator with a fit rule, of a large value, a constant mask and a negative constant.
PROGRAM = '''# pystachy: python-int
def rem(x: int, y: int) -> int:
    return x % y


def mask(x: int) -> int:
    return x & 0xFFFF


def shr(x: int, s: int) -> int:
    return x >> s


def both(x: int, y: int) -> int:
    return (x & y) + (y % 1000) + (x >> 3) + (-1 & x)


print(rem(2 ** 70 + 5, 7), mask(2 ** 70 + 0x1234), shr(2 ** 80, 70), both(2 ** 65 + 3, 12345))
'''


def compile_snapshot(source):
    with tempfile.TemporaryDirectory() as directory:
        program = Path(directory) / "fits.py"
        program.write_text(source)
        output = Path(directory) / "inspection"
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        completed = subprocess.run([sys.executable, str(ROOT / "tools" / "inspect_compiler.py"), str(program),
                                    "--output", str(output), "--typed-after-only"],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
        if completed.returncode != 0:
            raise AssertionError(completed.stdout + completed.stderr)
        return json.loads((output / "typed-after.json").read_text())


def function(snapshot, symbol):
    return next(fn for fn in snapshot["functions"] if fn["symbol"] == symbol)


def record(fields, symbol):
    return next(item for item in fields["functions"] if item["function"] == symbol)


def known_select(fn):
    """The function's one select of a null digit pointer for pys_big_op's result."""
    defs = definitions(fn)
    for block in fn["blocks"]:
        for op in block["operations"]:
            args = operands(op)
            if op["op"] == "select" and len(args) == 3 and args[1] == "null" and \
                    defs.get(args[2], {}).get("op") == "big.hi":
                return op, defs
    raise AssertionError("no known select")


def operand_source(defs, call, index):
    """The promoting int pys_big_op's operand index (0 or 1) is the word and digits of."""
    return operands(defs[operands(call)[2 * index]])[0]


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class FitClaimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = compile_snapshot(PROGRAM)

    def corrupted(self, symbol, change):
        snapshot = copy.deepcopy(self.snapshot)
        fn = function(snapshot, symbol)
        select, defs = known_select(fn)
        call = defs[operands(defs[operands(select)[2]])[0]]
        change(select, defs, call)
        return check_all(snapshot, CHECKER)

    def test_each_operator_claim_is_proved(self):
        fields, code = check_all(self.snapshot, CHECKER)
        self.assertEqual((fields["status"], code), ("accepted", 0), fields)
        claims = {fn["symbol"]: [claim for _, claim in known_claims(fn)] for fn in self.snapshot["functions"]}
        self.assertEqual([claim["op"] for claim in claims["@f.rem"]], ["%"])
        self.assertEqual(claims["@f.rem"][0]["cond"], "fitsY")
        self.assertEqual(claims["@f.shr"][0]["cond"], "fitsX")
        self.assertEqual(claims["@f.mask"][0]["cond"],
                         {"or": [{"and": ["fitsX", "nonnegX"]}, {"and": ["fitsY", "nonnegY"]}]})
        self.assertEqual(sorted(claim["op"] for claim in claims["@f.both"]), ["%", "&", "&", ">>"])
        self.assertEqual(fields["totals"]["proved_claims"], 7)

    def test_a_dividends_fit_does_not_bound_a_remainder(self):
        # (x % y's condition about x: the digits it tests are the dividend's)
        def change(select, defs, call):
            fits = defs[operands(select)[0]]
            hi = defs[operands(defs[operands(fits)[0]])[0]]
            hi["operands"][0]["value"] = operand_source(defs, call, 0)
        fields, code = self.corrupted("@f.rem", change)
        self.assertEqual((fields["status"], code), ("rejected", 1), fields)
        self.assertEqual(record(fields, "@f.rem")["unproved"][0]["cond"], "fitsX")

    def test_a_counts_fit_does_not_bound_a_shift(self):
        def change(select, defs, call):
            fits = defs[operands(select)[0]]
            hi = defs[operands(defs[operands(fits)[0]])[0]]
            hi["operands"][0]["value"] = operand_source(defs, call, 1)
        fields, code = self.corrupted("@f.shr", change)
        self.assertEqual((fields["status"], code), ("rejected", 1), fields)

    def test_a_words_sign_without_its_fit_does_not_bound_an_and(self):
        # (the condition's second disjunct reduced to the mask's word being nonnegative)
        def change(select, defs, call):
            either = defs[operands(select)[0]]
            second = defs[operands(either)[1]]
            either["operands"][1]["value"] = operands(second)[1]
        fields, code = self.corrupted("@f.mask", change)
        self.assertEqual((fields["status"], code), ("rejected", 1), fields)
        self.assertEqual(record(fields, "@f.mask")["unproved"][0]["cond"],
                         {"or": [{"and": ["fitsX", "nonnegX"]}, "nonnegY"]})

    def test_an_unconditional_null_is_rejected(self):
        def change(select, defs, call):
            select["operands"][0]["value"] = "true"
        fields, code = self.corrupted("@f.rem", change)
        self.assertEqual((fields["status"], code), ("rejected", 1), fields)

    def test_a_condition_outside_the_atoms_is_unsupported(self):
        # (a test of something else entirely: the checker must not guess what it means)
        def change(select, defs, call):
            fits = defs[operands(select)[0]]
            fits["text"] = "slt"
        fields, code = self.corrupted("@f.rem", change)
        self.assertEqual((fields["status"], code), ("unsupported", 2), fields)

    def test_a_null_for_an_operator_without_a_rule_is_unsupported(self):
        def change(select, defs, call):
            call["operands"][4]["value"] = "0"
        fields, code = self.corrupted("@f.rem", change)
        self.assertEqual((fields["status"], code), ("unsupported", 2), fields)


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class ModelOperatorTest(unittest.TestCase):
    """The model's operators (Int.fmod, Int.fdiv, >>>, pand, por, pxor) are CPython's."""

    VALUES = [0, 1, -1, 2, -2, 3, -7, 12345, -12345, 2 ** 62, -2 ** 62, 2 ** 63 - 1, -2 ** 63, 2 ** 63,
              -2 ** 63 - 1, 2 ** 64 - 1, 2 ** 64, -2 ** 64, 2 ** 64 + 5, -2 ** 70 + 3, 2 ** 100 - 1]
    COUNTS = [0, 1, 3, 62, 63, 64, 65, 100, -1]

    @staticmethod
    def python(op, x, y):
        try:
            return {"%": lambda: x % y, "//": lambda: x // y, ">>": lambda: x >> y, "<<": lambda: x << y,
                    "&": lambda: x & y, "|": lambda: x | y, "^": lambda: x ^ y}[op]()
        except (ZeroDivisionError, ValueError):
            return None

    def test_operators_match_cpython(self):
        items = [(op, x, y) for op in ("%", "//", "&", "|", "^") for x in self.VALUES for y in self.VALUES]
        items += [(op, x, s) for op in (">>", "<<") for x in self.VALUES for s in self.COUNTS]
        values = evaluate(CHECKER, items)
        mismatches = [(item, value, self.python(*item)) for item, value in zip(items, values, strict=True)
                      if value != self.python(*item)]
        self.assertEqual(mismatches, [])
        self.assertGreater(len(items), 1000)


class AdapterUnitTest(unittest.TestCase):
    def test_rule_codes_follow_bigints(self):
        sys.path.insert(0, str(ROOT / "src"))
        from pystachy_compiler.bigints import BIGOPS
        self.assertEqual({op: BIGOPS[op] for op in check_lean_int.RULES.values()},
                         {op: code for code, op in check_lean_int.RULES.items()})


if __name__ == "__main__":
    unittest.main()
