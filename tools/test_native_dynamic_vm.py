"""Pure scalar baseline contracts; these host-side tests do not require LLVM."""
import math
import random
import textwrap
import unittest

from native_dynamic_vm import (
    I64_MAX,
    I64_MIN,
    Program,
    dyn_bool,
    dyn_float,
    dyn_int,
    dyn_none,
    dyn_repr,
    dyn_str,
    truth,
)


def program(source, **kwargs):
    return Program(textwrap.dedent(source), **kwargs)


class NativeDynamicBaselineTests(unittest.TestCase):
    def test_scalar_truth_and_tags(self):
        values = [dyn_none(), dyn_bool(False), dyn_int(0), dyn_float(0.0), dyn_str("")]
        self.assertEqual([value.tag for value in values], ["None", "bool", "int", "float", "str"])
        self.assertTrue(all(not truth(value) for value in values))
        for value in [dyn_bool(True), dyn_int(-1), dyn_float(-0.1), dyn_str("x")]:
            self.assertTrue(truth(value))
        self.assertEqual(dyn_repr(dyn_str("quoted ' text")), repr("quoted ' text"))
        p = program("def both(a,b):\n    return a&b\n")
        self.assertEqual(p.execute("both", [dyn_bool(True), dyn_bool(False)]).tag, "bool")
        self.assertEqual(p.execute("both", [dyn_bool(True), dyn_int(3)]).tag, "int")

    def test_annotations_are_inert_baseline_metadata(self):
        # Baseline execution discovers actual tags; annotations are never evaluated
        # or enforced. The native specialization layer separately restricts them.
        p = program("""
            def echo(value: int) -> int:
                local: float = value
                return local
        """)
        value = p.execute("echo", [dyn_str("actual runtime tag")])
        self.assertEqual((value.tag, value.text), ("str", "actual runtime tag"))

    def test_direct_helpers_and_call_observations(self):
        p = program("""
            def square(x):
                return x*x
            def sumsq(n):
                total = 0
                i = 0
                while i < n:
                    total += square(i)
                    i += 1
                return total
        """)
        self.assertEqual(p.execute("sumsq", [dyn_int(10)]).integer, sum(i*i for i in range(10)))
        self.assertEqual(p.baseline_calls, {"sumsq": 1, "square": 10})
        self.assertEqual(p.execute("square", [dyn_float(1.5)]).real, 2.25)

    def test_local_types_can_change_across_branches(self):
        p = program("""
            def mixed(n):
                value = n
                if n > 0:
                    value = 'warm'
                return value
        """)
        self.assertEqual(p.execute("mixed", [dyn_int(-2)]).integer, -2)
        value = p.execute("mixed", [dyn_int(2)])
        self.assertEqual((value.tag, value.text), ("str", "warm"))

    def test_short_circuit_preserves_operand_and_skips_failure(self):
        p = program("""
            def and_test(x):
                return x and (1//0)
            def or_test(x):
                return x or (1//0)
            def choose(x):
                return 'yes' if x else 'no'
        """)
        value = p.execute("and_test", [dyn_int(0)])
        self.assertEqual((value.tag, value.integer), ("int", 0))
        self.assertEqual(p.execute("or_test", [dyn_str("first")]).text, "first")
        self.assertEqual(p.execute("choose", [dyn_none()]).text, "no")
        with self.assertRaises(ZeroDivisionError):
            p.execute("and_test", [dyn_int(1)])

    def test_loop_break_continue_and_else(self):
        p = program("""
            def descending(n):
                total = 0
                for i in range(n, 0, -1):
                    if i == 4:
                        continue
                    if i == 2:
                        break
                    total += i
                else:
                    total += 100
                return total
            def ascending(n):
                total = 0
                i = 0
                while i < n:
                    i += 1
                    if i == 2:
                        continue
                    total += i
                else:
                    total += 100
                return total
        """)
        self.assertEqual(p.execute("descending", [dyn_int(5)]).integer, 8)
        self.assertEqual(p.execute("descending", [dyn_int(1)]).integer, 101)
        self.assertEqual(p.execute("ascending", [dyn_int(3)]).integer, 104)

    def test_range_stops_at_i64_boundaries_without_overflow(self):
        p = program("""
            def count(start, stop, step):
                total = 0
                for i in range(start, stop, step):
                    total += 1
                else:
                    total += 10
                return total
            def argument_failure():
                for i in range(1.0, 1//0):
                    pass
        """)
        for args in [(I64_MAX-1, I64_MAX, 2), (I64_MIN+1, I64_MIN, -2), (0, I64_MIN, I64_MIN)]:
            with self.subTest(args=args):
                self.assertEqual(p.execute("count", [dyn_int(v) for v in args]).integer, len(range(*args)) + 10)
        with self.assertRaises(ValueError):
            p.execute("count", [dyn_int(0), dyn_int(2), dyn_int(0)])
        # Evaluate every argument before range applies its integer type checks.
        with self.assertRaises(ZeroDivisionError):
            p.execute("argument_failure", [])

    def test_literals_and_checked_add_subtract_negation(self):
        p = program("""
            def minimum():
                return -9223372036854775808
            def maximum():
                return 0x7fff_ffff_ffff_ffff
            def add(a, b):
                return a+b
            def sub(a, b):
                return a-b
            def neg(a):
                return -a
        """)
        self.assertEqual(p.execute("minimum", []).integer, I64_MIN)
        self.assertEqual(p.execute("maximum", []).integer, I64_MAX)
        self.assertEqual(p.execute("add", [dyn_int(I64_MIN), dyn_int(I64_MAX)]).integer, -1)
        self.assertEqual(p.execute("sub", [dyn_int(I64_MIN), dyn_int(I64_MIN)]).integer, 0)
        for name, args in [("add", [I64_MAX, 1]), ("add", [I64_MIN, -1]),
                           ("sub", [I64_MIN, 1]), ("sub", [I64_MAX, -1]), ("neg", [I64_MIN])]:
            with self.subTest(name=name, args=args), self.assertRaises(OverflowError):
                p.execute(name, [dyn_int(v) for v in args])
        with self.assertRaises(OverflowError):
            program("def f():\n    return 9223372036854775808\n")

    def test_checked_multiplication_against_exact_integer_oracle(self):
        p = program("def mul(a, b):\n    return a*b\n")
        boundaries = [I64_MIN, I64_MIN+1, -4611686018427387904, -3, -2, -1,
                      0, 1, 2, 3, 4611686018427387904, I64_MAX-1, I64_MAX]
        pairs = [(a, b) for a in boundaries for b in boundaries]
        rng = random.Random(374)
        pairs += [(rng.randint(I64_MIN, I64_MAX), rng.randint(-1000, 1000)) for _ in range(200)]
        for a, b in pairs:
            expected = a*b  # CPython's arbitrary-precision arithmetic is the oracle.
            with self.subTest(a=a, b=b):
                if expected < I64_MIN or expected > I64_MAX:
                    with self.assertRaises(OverflowError):
                        p.execute("mul", [dyn_int(a), dyn_int(b)])
                else:
                    self.assertEqual(p.execute("mul", [dyn_int(a), dyn_int(b)]).integer, expected)

    def test_integer_division_modulo_and_overflow(self):
        p = program("""
            def quotient(a, b):
                return a//b
            def remainder(a, b):
                return a%b
        """)
        for a, b in [(-7, 3), (7, -3), (-7, -3), (I64_MIN, 3), (I64_MAX, -3)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(p.execute("quotient", [dyn_int(a), dyn_int(b)]).integer, a//b)
                self.assertEqual(p.execute("remainder", [dyn_int(a), dyn_int(b)]).integer, a % b)
        with self.assertRaises(OverflowError):
            p.execute("quotient", [dyn_int(I64_MIN), dyn_int(-1)])
        self.assertEqual(p.execute("remainder", [dyn_int(I64_MIN), dyn_int(-1)]).integer, 0)
        for name in ["quotient", "remainder"]:
            with self.subTest(name=name), self.assertRaises(ZeroDivisionError):
                p.execute(name, [dyn_int(1), dyn_int(0)])

    def test_exact_int_float_comparisons_and_unordered_nan(self):
        p = program("""
            def equal(a, b):
                return a==b
            def less(a, b):
                return a<b
            def less_equal(a, b):
                return a<=b
        """)
        pairs = [(I64_MAX, float(I64_MAX)), (I64_MIN, float(I64_MIN)),
                 (2**53+1, float(2**53)), (0, -0.5), (-1, -0.5),
                 (1, math.inf), (1, -math.inf), (1, math.nan)]
        for integer, real in pairs:
            for name, expected in [("equal", integer == real), ("less", integer < real),
                                   ("less_equal", integer <= real)]:
                with self.subTest(name=name, integer=integer, real=real):
                    actual = p.execute(name, [dyn_int(integer), dyn_float(real)])
                    self.assertEqual(truth(actual), expected)
            for name, expected in [("equal", real == integer), ("less", real < integer),
                                   ("less_equal", real <= integer)]:
                with self.subTest(name=name, real=real, integer=integer, reverse=True):
                    actual = p.execute(name, [dyn_float(real), dyn_int(integer)])
                    self.assertEqual(truth(actual), expected)
        self.assertTrue(truth(p.execute("equal", [dyn_bool(True), dyn_float(1.0)])))
        self.assertFalse(truth(p.execute("equal", [dyn_float(math.nan), dyn_float(math.nan)])))

    def test_unbound_locals_implicit_none_and_scalar_builtins(self):
        p = program("""
            def unbound(flag):
                if flag:
                    value = 1
                return value
            def empty():
                pass
            def builtins(text):
                return str(abs(-len(text)))
            def singleton(value):
                return value is None
        """)
        with self.assertRaises(UnboundLocalError):
            p.execute("unbound", [dyn_bool(False)])
        self.assertEqual(p.execute("empty", []).tag, "None")
        self.assertEqual(p.execute("builtins", [dyn_str("abc")]).text, "3")
        self.assertFalse(truth(p.execute("singleton", [dyn_int(7)])))
        self.assertTrue(truth(p.execute("singleton", [dyn_none()])))

    def test_unsupported_regions_reject_before_any_execution(self):
        rejected = [
            "def bad():\n    import os\n    return 1\n",
            "def bad():\n    global value\n    value=1\n",
            "def bad(x=1):\n    return x\n",
            "def helper(x):\n    return x\ndef bad():\n    return helper(x=1)\n",
            "def bad(x):\n    print(x)\n    return x\n",
            "def bad(x):\n    x.field=1\n    return x\n",
            "def bad(x):\n    return x[0]\n",
            "def bad():\n    return [1,2]\n",
            "value=1\ndef bad():\n    return value\n",
            "@unknown\ndef bad():\n    return 1\n",
            "def _psdyn_forged():\n    return 1\n",
            "def pys_dynamic_forged():\n    return 1\n",
            "def psdyn_forged():\n    return 1\n",
            "def pys_floordiv(a: int, b: int) -> int:\n    return 999\ndef divide(a,b):\n    return a//b\n",
            "def helper(x):\n    return x\ndef bad():\n    helper=1\n    return helper(2)\n",
        ]
        # Even an unused unsupported definition makes construction fail. No input
        # function runs while the complete module is parsed and validated.
        for source in rejected:
            with self.subTest(source=source), self.assertRaises(ValueError):
                Program("def safe():\n    return 1//0\n" + source)

    def test_fuel_exhaustion_resets_execution_state(self):
        p = program("""
            def spin():
                while True:
                    pass
            def done():
                return 7
        """, max_steps=30)
        with self.assertRaisesRegex(RuntimeError, "step limit"):
            p.execute("spin", [])
        self.assertEqual(p.depth, 0)
        self.assertEqual(p.execute("done", []).integer, 7)
        self.assertLess(p.steps, 30)

    def test_recursion_limit_restores_depth_after_failure(self):
        p = program("""
            def recursive(n):
                if n == 0:
                    return 0
                return recursive(n-1)
        """, max_depth=8)
        self.assertEqual(p.execute("recursive", [dyn_int(4)]).integer, 0)
        with self.assertRaisesRegex(RecursionError, "recursion limit"):
            p.execute("recursive", [dyn_int(20)])
        self.assertEqual(p.depth, 0)
        self.assertEqual(p.execute("recursive", [dyn_int(0)]).integer, 0)


if __name__ == "__main__":
    unittest.main()
