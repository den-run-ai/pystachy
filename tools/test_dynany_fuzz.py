"""Unit tests of tools/dynany_fuzz.py's generator and comparison, which need no compiler."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynany_fuzz as fz


class GeneratorTest(unittest.TestCase):
    def test_deterministic(self) -> None:
        self.assertEqual(fz.program(4, 60), fz.program(4, 60))
        self.assertNotEqual(fz.program(4, 60)[0], fz.program(5, 60)[0])

    def test_left_out(self) -> None:
        plain = ("Plain()", "plain")
        big = ("9223372036854775807", "bigint")
        self.assertFalse(fz.allowed("repr({})", plain, ("", "")))
        self.assertFalse(fz.allowed("hash({})", ("'a'", "str"), ("", "")))
        self.assertTrue(fz.allowed("hash({})", ("1.5", "float"), ("", "")))
        self.assertFalse(fz.allowed("hash({})", ("float('nan')", "float"), ("", "")))
        self.assertFalse(fz.allowed("*", ("[1]", "list"), big))
        self.assertFalse(fz.allowed("**", ("2", "int"), big))
        self.assertFalse(fz.allowed("[]", ("{}", "dict"), plain))
        self.assertTrue(fz.allowed("+", ("2", "int"), big))
        for src, cases in [fz.program(seed, 200) for seed in (1, 2, 3)]:
            for expr, op, kind, _, _ in cases:
                self.assertFalse(op in ("repr({})", "str({})") and kind == "plain", expr)

    def test_cpython_runs_it(self) -> None:
        # (every case prints one line, its result or its exception, and no invariant fails)
        src, cases = fz.program(7, 80)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prog.py")
            with open(path, "w") as f:
                f.write(src)
            p = subprocess.run(fz.CPYTHON + [path], capture_output=True, text=True, cwd=d)
        self.assertEqual(p.returncode, 0, p.stderr)
        got, other = fz.by_case(p.stdout)
        self.assertEqual(other, [])
        self.assertEqual(sorted(got), list(range(len(cases))))
        self.assertTrue(all(len(v) == 1 for v in got.values()), p.stdout)

    def test_bool_inversion_warning(self) -> None:
        # (CPython's DeprecationWarning of ~ of a bool, which Pystachy does not give, is no line)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "inv.py")
            with open(path, "w") as f:
                f.write("from typing import Any\nb: Any = True\nprint(0, ~b)\n")
            self.assertEqual(fz.run(fz.CPYTHON + [path], d), (0, "0 -2\n"))

    def test_inplace_alias(self) -> None:
        # (an in-place case checks its invariants against its left operand as it was)
        src, cases = fz.program(3, 150)
        k = [i for i, c in enumerate(cases) if c[1].endswith("=") and c[1] not in ("==", "!=", "<=", ">=")][0]
        self.assertIn(f"    l{k}: Any = r{k}\n", src)
        self.assertIn(f"    inv({k}, r{k}, l{k})\n", src)


class CompareTest(unittest.TestCase):
    cases = [("v1 + v2", "+", "int", "1", "v1"), ("v3 % v4", "%", "str", "'a'", "v3"), ("v5 * v6", "*", "bigint", "9223372036854775807", "v5")]

    def test_same(self) -> None:
        out = "0 3\n1 'a1'\n2 18446744073709551614\n"
        self.assertEqual(fz.compare(1, self.cases, "jit", (0, out), (0, out)), [])

    def test_expected(self) -> None:
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        ps = "0 3\n1 TypeError: unsupported operand type(s) for %: 'str' and 'int'\n2 OverflowError: integer overflow\n"
        self.assertEqual(fz.compare(1, self.cases, "jit", (0, cp), (0, ps)), [])

    def test_str_mod(self) -> None:
        # (% of an Any str: only the deviation's own TypeError, for its operator, where CPython
        # formats or raises another error)
        mod = "1 TypeError: unsupported operand type(s) for %: 'str' and 'int'\n"
        own = "1 TypeError: not all arguments converted during string formatting\n"
        self.assertEqual(fz.compare(1, self.cases[:2], "jit", (0, "0 3\n" + own), (0, "0 3\n" + mod)), [])
        self.assertEqual(len(fz.compare(1, self.cases[:2], "jit", (0, "0 3\n1 'a1'\n"), (0, "0 3\n" + own))), 1)
        c = [("v3 %= v4", "%=", "str", "'a'", "v3")]
        self.assertEqual(fz.compare(1, c, "jit", (0, "0 'a1'\n"), (0, "0 TypeError: unsupported operand type(s) for %=: 'str' and 'int'\n")), [])
        self.assertEqual(len(fz.compare(1, c, "jit", (0, "0 'a1'\n"), (0, "0 TypeError: unsupported operand type(s) for %: 'str' and 'int'\n"))), 1)
        # (and it names the right operand's type: v4 holds an int)
        wrong = "1 TypeError: unsupported operand type(s) for %: 'str' and 'dict'\n"
        self.assertEqual(len(fz.compare(1, self.cases[:2], "jit", (0, "0 3\n" + own), (0, "0 3\n" + wrong))), 1)

    def test_type_name(self) -> None:
        # (the name of each pool value's type is CPython's)
        ns: dict[str, object] = {}
        exec(fz.PRELUDE, ns)
        for src, kind in fz.POOL:
            self.assertEqual(fz.type_name(src, kind), type(eval(src, ns)).__name__, src)

    def test_build_output(self) -> None:
        # (a build that succeeds and prints something is a mismatch; a failed one is compare()'s)
        self.assertEqual(fz.built(1, (0, "")), [])
        self.assertEqual(len(fz.built(1, (0, "runtime.c:1:1: runtime error: something\n"))), 1)
        self.assertEqual(fz.built(1, (1, "error\n")), [])

    def test_mismatch(self) -> None:
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        ps = "0 4\n1 'a1'\n2 OverflowError: integer overflow\n0 INVARIANT: is and id() disagree\n"
        bad = fz.compare(1, self.cases, "jit", (0, cp), (0, ps))
        self.assertEqual(len(bad), 1)
        self.assertIn("case 0: v1 + v2", bad[0])
        self.assertEqual(len(fz.compare(1, self.cases, "aot", (0, cp), (1, cp))), 1)

    def test_complex(self) -> None:
        # (a negative number to a fractional power: CPython's complex result, Pystachy's ValueError)
        c = [("v2 ** v19", "**", "int", "-1", "v2")]
        cp = "0 (0.7071067811865477-0.7071067811865474j)\n"
        ps = "0 ValueError: a negative number to a fractional power has a complex result (not supported)\n"
        self.assertEqual(fz.compare(1, c, "jit", (0, cp), (0, ps)), [])
        self.assertEqual(len(fz.compare(1, c, "jit", (0, "0 0.5\n"), (0, ps))), 1)

    def test_fails_closed(self) -> None:
        # (a line that names no case, or a case the program does not have, is a mismatch)
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        warn = "0 3\nruntime warning: something\n1 'a1'\n2 OverflowError: integer overflow\n"
        self.assertEqual(len(fz.compare(1, self.cases, "jit", (0, cp), (0, warn))), 1)
        extra = cp + "7 INVARIANT: is and id() disagree\n"
        self.assertEqual(len(fz.compare(1, self.cases, "jit", (0, cp), (0, extra))), 1)

    def test_order(self) -> None:
        # (each case's lines alike, but printed in another order, is a mismatch)
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        ps = "1 'a1'\n0 3\n2 18446744073709551614\n"
        self.assertEqual(len(fz.compare(1, self.cases, "jit", (0, cp), (0, ps))), 1)

    def test_compiler_cmd(self) -> None:
        # (a word of --compiler that names a file is made absolute, as the programs run elsewhere;
        # quoting as a shell does)
        here = os.path.relpath(os.path.abspath(fz.__file__))
        self.assertEqual(fz.compiler_cmd(f"python3 '{here}'"), ["python3", os.path.abspath(here)])
        self.assertEqual(fz.compiler_cmd("no-such-compiler --flag"), ["no-such-compiler", "--flag"])

    def test_big_int(self) -> None:
        self.assertTrue(fz.big_int("3 9223372036854775808"))
        self.assertTrue(fz.big_int("3 -9223372036854775809"))
        self.assertFalse(fz.big_int("3 9223372036854775807"))
        self.assertFalse(fz.big_int("3 1.5"))
        # (past the 4,300 digits int() reads: 2 ** 63 to the 1000th power has 18,965)
        self.assertTrue(fz.big_int("3 -1" + "0" * 18964))

    def test_int_digits(self) -> None:
        # (CPython prints an int of any number of digits, as Pystachy's OverflowError rule expects)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "big.py")
            with open(path, "w") as f:
                f.write("print(0, 10 ** 5000 + 1)\n")
            self.assertEqual(fz.run(fz.CPYTHON + [path], d), (0, "0 1" + "0" * 4999 + "1\n"))


if __name__ == "__main__":
    unittest.main()
