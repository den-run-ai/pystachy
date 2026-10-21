"""Unit tests of tools/dynany_fuzz.py's generator and comparison, which need no compiler."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynany_fuzz as fz  # noqa: E402


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
            p = subprocess.run([sys.executable, "-I", path], capture_output=True, text=True, cwd=d)
        self.assertEqual(p.returncode, 0, p.stderr)
        got = fz.by_case(p.stdout)
        self.assertEqual(sorted(got), list(range(len(cases))))
        self.assertTrue(all(len(v) == 1 for v in got.values()), p.stdout)


class CompareTest(unittest.TestCase):
    cases = [("v1 + v2", "+", "int", "1", "v1"), ("v3 % v4", "%", "str", "'a'", "v3"), ("v5 * v6", "*", "bigint", "9223372036854775807", "v5")]

    def test_same(self) -> None:
        out = "0 3\n1 'a1'\n2 18446744073709551614\n"
        self.assertEqual(fz.compare(1, self.cases, "jit", (0, out), (0, out)), [])

    def test_expected(self) -> None:
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        ps = "0 3\n1 TypeError: not all arguments converted during string formatting\n2 OverflowError: integer overflow\n"
        self.assertEqual(fz.compare(1, self.cases, "jit", (0, cp), (0, ps)), [])

    def test_mismatch(self) -> None:
        cp = "0 3\n1 'a1'\n2 18446744073709551614\n"
        ps = "0 4\n1 'a1'\n2 OverflowError: integer overflow\n0 INVARIANT: is and id() disagree\n"
        bad = fz.compare(1, self.cases, "jit", (0, cp), (0, ps))
        self.assertEqual(len(bad), 1)
        self.assertIn("case 0: v1 + v2", bad[0])
        self.assertEqual(len(fz.compare(1, self.cases, "aot", (0, cp), (1, cp))), 1)

    def test_big_int(self) -> None:
        self.assertTrue(fz.big_int("3 9223372036854775808"))
        self.assertTrue(fz.big_int("3 -9223372036854775809"))
        self.assertFalse(fz.big_int("3 9223372036854775807"))
        self.assertFalse(fz.big_int("3 1.5"))


if __name__ == "__main__":
    unittest.main()
