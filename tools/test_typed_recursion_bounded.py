"""Bounded recursion regions keep their complete guarded fallback."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.test_typed_recursion import compile_source, operations
from src.pystachy_compiler.specs import FXBIT


ORDINARY = '''
def step(value: int) -> int:
    return value + 1

def kernel(n: int) -> int:
    value = 0
    for i in range(n):
        value = step(value)
    return value

print(kernel(3))
'''


class TypedRecursionBoundedTests(unittest.TestCase):
    def test_straight_line_helper_does_not_pay_an_unamortized_selector(self):
        source = '''
def leaf(n: int) -> int:
    return n + 1
def helper(n: int) -> int:
    return leaf(n)
print(helper(3))
'''
        enabled, _ = compile_source(source)
        disabled, _ = compile_source(source, opt="-recursionregion")
        self.assertEqual(enabled, disabled)

    def test_unrelated_loop_does_not_make_a_single_call_profitable(self):
        source = '''
def leaf(n: int) -> int:
    return n + 1
def helper(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
    return leaf(total)
print(helper(3))
'''
        enabled, _ = compile_source(source)
        disabled, _ = compile_source(source, opt="-recursionregion")
        self.assertEqual(enabled, disabled)

    def test_repeated_calls_share_one_nonraising_bound_and_unchecked_callees(self):
        ir, functions = compile_source(ORDINARY)
        original = functions["@f.kernel"]
        rooms = [(label, at, fx) for label, _, code in original["blocks"]
                 for at, (op, name, fx) in enumerate(code)
                 if (op, name) == ("rt", "recursion.room")]
        self.assertEqual(len(rooms), 1)
        label, at, fx = rooms[0]
        self.assertEqual(label, "entry")
        self.assertEqual(original["operands"][(label, at)][0], ["2"])
        self.assertFalse(fx & FXBIT["R"])
        self.assertTrue(fx & FXBIT["I"])
        self.assertTrue(any(op[:2] == ("call", "@f.step") for op in operations(original)))
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter") for op in operations(original)))
        fast = functions["@rf.f.kernel"]
        self.assertTrue(any(op[:2] == ("call", "@rf.f.step") for op in operations(fast)))
        for name in ("@rf.f.kernel", "@rf.f.step"):
            self.assertFalse(any(op == "rt" and symbol.startswith("recursion.")
                                 for op, symbol, _ in operations(functions[name])), name)
        definition = next(line for line in ir.splitlines()
                          if line.startswith("define ") and "@pys.recursion.room(" in line)
        self.assertIn("alwaysinline", definition)
        self.assertIn("nounwind", definition)
        helper = ir.split(definition, 1)[1].split("\n}", 1)[0]
        self.assertNotIn("@pys_recursion_error", helper)
        self.assertNotIn("store ", helper)

    def test_disable_restores_the_previous_guarded_shape(self):
        ir, functions = compile_source(ORDINARY, opt="-recursionregion")
        self.assertNotIn("@rf.", ir)
        self.assertFalse(any(op[:2] == ("rt", "recursion.room")
                             for fn in functions.values() for op in operations(fn)))
        self.assertTrue(any(op[:2] == ("rt", "recursion.check")
                            for op in operations(functions["@f.step"])))

    def test_transitive_depth_counts_each_source_function_once(self):
        _, functions = compile_source('''
def leaf(n: int) -> int:
    return n + 1

def middle(n: int) -> int:
    return leaf(n)

def outer(n: int) -> int:
    value = 0
    for i in range(n):
        value += middle(i)
    return value

print(outer(3))
''')
        fn = functions["@f.outer"]
        bounds = [fn["operands"][(label, at)][0]
                  for label, _, code in fn["blocks"] for at, op in enumerate(code)
                  if op[:2] == ("rt", "recursion.room")]
        self.assertEqual(bounds, [["3"]])
        self.assertTrue(any(op[:2] == ("call", "@rf.f.middle")
                            for op in operations(functions["@rf.f.outer"])))
        self.assertTrue(any(op[:2] == ("call", "@rf.f.leaf")
                            for op in operations(functions["@rf.f.middle"])))

    def test_recursive_cycles_and_their_callers_keep_guards(self):
        _, functions = compile_source('''
def first(n: int) -> int:
    if n == 0:
        return 1
    return second(n - 1)

def second(n: int) -> int:
    return first(n)

def caller(n: int) -> int:
    return first(n)

print(caller(2))
''')
        for name in ("first", "second", "caller"):
            self.assertNotIn("@rf.f." + name, functions)
            self.assertFalse(any(op[:2] == ("rt", "recursion.room")
                                 for op in operations(functions["@f." + name])))

    def test_indirect_calls_limit_changes_and_cleanup_are_boundaries(self):
        _, functions = compile_source('''
from collections.abc import Callable
import sys

def leaf(n: int) -> int:
    return n + 1

def indirect(f: Callable[[int], int], n: int) -> int:
    return f(n)

def changes(n: int) -> int:
    sys.setrecursionlimit(n)
    return leaf(n)

def cleanup(n: int) -> int:
    try:
        return leaf(n)
    finally:
        sys.setrecursionlimit(1000)

print(indirect(leaf, 1), changes(1000), cleanup(2))
''')
        for name in ("indirect", "changes", "cleanup"):
            self.assertNotIn("@rf.f." + name, functions)
            self.assertTrue(any(op[:2] == ("rt", "recursion.enter")
                                for op in operations(functions["@f." + name])))

    def test_guarded_entry_remains_before_body_effects_on_the_slow_path(self):
        _, functions = compile_source('''
seen: list[int] = [0]

def leaf(n: int) -> int:
    return n + 1

def kernel(n: int) -> int:
    seen[0] += 1
    if n < 0:
        return 0
    total = 0
    for i in range(n):
        total += leaf(i)
    return total

print(kernel(3))
''')
        fn = functions["@f.kernel"]
        slow = [(label, code) for label, _, code in fn["blocks"]
                if any(op[:2] == ("rt", "recursion.enter") for op in code)]
        self.assertEqual(len(slow), 1)
        self.assertNotEqual(slow[0][0], "entry")
        self.assertEqual(slow[0][1][0][:2], ("rt", "recursion.enter"))
        self.assertTrue(any(op[:2] == ("call", "@f.leaf") for op in operations(fn)))

    def test_native_file_programs_remain_fully_guarded(self):
        source = ORDINARY + '''
stream = open("/dev/null", "w")
stream.write("x")
stream.close()
'''
        optimized, _ = compile_source(source)
        guarded, _ = compile_source(source, opt="-recursionleaf,-recursionregion")
        self.assertEqual(optimized, guarded)

    def test_scoped_file_root_allows_the_bounded_kernel(self):
        source = ORDINARY + '''
with open("/dev/null", "w") as stream:
    stream.write(str(kernel(2)))
'''
        ir, functions = compile_source(source)
        self.assertIn("@pys_unwind_file(", ir)
        self.assertIn("@rf.f.kernel", functions)
        self.assertTrue(any(op[:2] == ("rt", "recursion.room")
                            for op in operations(functions["@f.kernel"])))

    def test_cloned_calls_forward_numeric_identity_parameters(self):
        ir, functions = compile_source('''
# pystachy: dynamic-any
# pystachy: python-int
from typing import Any

def leaf(n: int) -> int:
    return n

def relay(n: int) -> int:
    for i in range(2):
        n = leaf(n)
    return n

value: Any = 123456789012345678901234567890
alias: Any = relay(value)
print(value is alias)
''')
        # The hidden identity arguments must have the same ABI in both versions.
        originals = {}
        fast = {}
        for line in ir.splitlines():
            match = re.match(r"define internal (.*?) @(rf\.)?(f\.(?:leaf|relay))\((.*?)\)", line)
            if match:
                (fast if match.group(2) else originals)[match.group(3)] = (match.group(1), match.group(4))
        self.assertIn("@rf.f.relay", functions)
        self.assertEqual(fast, originals)


if __name__ == "__main__":
    unittest.main()
