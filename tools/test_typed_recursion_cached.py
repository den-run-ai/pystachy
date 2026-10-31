"""Successful child calls prove later leaf checks redundant in an active frame."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.test_typed_recursion import compile_source, operations


PREFIX = '''
def leaf(value: int) -> int:
    return value + 1

def recursive(n: int) -> int:
    if n <= 0:
        return 0
    return recursive(n - 1) + 1
'''


class TypedRecursionCachedTests(unittest.TestCase):
    def test_checked_leaf_shares_exact_identity_signature(self):
        ir, functions = compile_source("# pystachy: dynamic-any\n" + PREFIX + '''
def kernel(n: int) -> int:
    total = leaf(0)
    for i in range(n):
        total += leaf(i) + recursive(i)
    return total
print(kernel(3))
''')
        self.assertEqual([op[:2] for op in operations(functions["@f.leaf"])],
                         [("rt", "recursion.check"), ("call", "@rc.f.leaf"), ("ret", "")])
        body = re.search(r"^define internal i64 @f\.leaf\(.*?^}", ir, re.M | re.S).group(0)
        self.assertNotIn("alloca", body)
        self.assertIn("musttail call i64 @rc.f.leaf(i64 %a0, ptr %aid0, ptr %idret)", body)
        self.assertLess(body.index("@pys.recursion.check()"), body.index("musttail call"))

    def test_successful_preheader_call_removes_only_later_checks(self):
        _, functions = compile_source(PREFIX + '''
def kernel(n: int) -> int:
    total = leaf(0)
    for i in range(n):
        total += leaf(i)
        total += recursive(i)
    return total
print(kernel(3))
''')
        ops = operations(functions["@f.kernel"])
        self.assertEqual(sum(op[:2] == ("call", "@f.leaf") for op in ops), 1)
        self.assertEqual(sum(op[:2] == ("call", "@rc.f.leaf") for op in ops), 1)
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter") for op in ops))
        self.assertFalse(any(op[:2] == ("rt", "recursion.room") for op in ops))
        self.assertTrue(any(op[:2] == ("rt", "recursion.check") for op in operations(functions["@f.leaf"])))
        self.assertFalse(any(op[:2] == ("rt", "recursion.check") for op in operations(functions["@rc.f.leaf"])))

    def test_loop_backedge_does_not_prove_its_own_first_call(self):
        _, functions = compile_source(PREFIX + '''
def kernel(n: int) -> int:
    total = 0
    for i in range(n):
        total += leaf(i)
        total += recursive(i)
    return total
print(kernel(3))
''')
        self.assertFalse(any(name.startswith("@rc.") for name in functions))

    def test_all_incoming_paths_need_a_successful_call(self):
        _, functions = compile_source(PREFIX + '''
def kernel(n: int, warm: bool) -> int:
    total = 0
    if warm:
        total += leaf(0)
    for i in range(n):
        total += leaf(i)
        total += recursive(i)
    return total
print(kernel(3, False))
''')
        self.assertFalse(any(name.startswith("@rc.") for name in functions))

    def test_unknown_callback_invalidates_even_through_source_helper(self):
        _, functions = compile_source(PREFIX + '''
from collections.abc import Callable

def helper(callback: Callable[[], int]) -> int:
    return callback()

def kernel(n: int, callback: Callable[[], int]) -> int:
    total = leaf(0)
    for i in range(n):
        total += helper(callback)
        total += leaf(i)
    return total
print(kernel(3, lambda: 1))
''')
        self.assertFalse(any(name.startswith("@rc.") for name in functions))

    def test_public_setter_preserves_room_after_successful_child(self):
        _, functions = compile_source(PREFIX + '''
import sys

def setter() -> int:
    try:
        sys.setrecursionlimit(1000)
        raise ValueError("caught")
    except ValueError:
        return 1

def kernel(n: int) -> int:
    total = leaf(0)
    for i in range(n):
        total += setter()
        total += leaf(i)
    return total
print(kernel(3))
''')
        self.assertTrue(any(op[:2] == ("call", "@rc.f.leaf") for op in operations(functions["@f.kernel"])))

    def test_handler_root_and_disabled_regions_retain_checks(self):
        source = PREFIX + '''
def kernel(n: int) -> int:
    total = leaf(0)
    for i in range(n):
        try:
            total += recursive(i)
        except RecursionError:
            total += 1
        total += leaf(i)
    return total
print(kernel(3))
'''
        for opt in ("", "-recursionregion", "-recursionleaf", "-all"):
            _, functions = compile_source(source, opt=opt)
            self.assertFalse(any(name.startswith("@rc.") for name in functions))

    def test_tuple_clone_keeps_fresh_aggregate_return(self):
        source = PREFIX.replace("    return value + 1", "    return (value, value + 1)", 1).replace(
            "def leaf(value: int) -> int:", "def leaf(value: int) -> tuple[int, int]:") + """
def kernel(n: int) -> int:
    left, right = leaf(0)
    total = left + right
    for i in range(n):
        left, right = leaf(i)
        total += left + right + recursive(i)
    return total
print(kernel(3))
"""
        ir, functions = compile_source(source)
        self.assertIn("@rc.f.leaf", functions)
        self.assertIn("call {i64, i64} @v.rc.f.leaf(", ir)
        self.assertTrue(any(op[0] == "alloc.fixed" for op in operations(functions["@f.leaf"])))
        self.assertNotIn("musttail call ptr @rc.f.leaf", ir)

    def test_terminal_child_keeps_single_frame_publication(self):
        source = PREFIX + '''
def problem() -> ValueError:
    return ValueError("failed")

def cold(value: int) -> int:
    if value < 0:
        raise problem()
    return value + 1

def kernel(n: int) -> int:
    total = leaf(0)
    for i in range(n):
        total += cold(i)
        total += recursive(i)
    return total
print(kernel(3))
'''
        ir, functions = compile_source(source)
        cold = operations(functions["@rc.f.cold"])
        self.assertFalse(any(op[:2] == ("rt", "recursion.check") for op in cold))
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter") for op in cold))
        self.assertTrue(any(op[:2] == ("call", "@f.problem") for op in cold))
        self.assertFalse(any(op[:2] == ("rt", "recursion.depth") for op in cold))
        self.assertEqual([op[:2] for op in operations(functions["@f.cold"])],
                         [("rt", "recursion.check"), ("call", "@rc.f.cold"), ("ret", "")])
        body = re.search(r"^define internal i64 @f\.cold\(.*?^}", ir, re.M | re.S).group(0)
        self.assertIn("musttail call i64 @rc.f.cold(i64 %a0)", body)


if __name__ == "__main__":
    unittest.main()
