"""Partial depth proofs publish before every observer and never resume unchecked."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.test_typed_recursion import compile_source, operations
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.optimizations import recursion_copy


PARTIAL = '''
import sys

def make_error() -> ValueError:
    return ValueError("cold")

def cold_leaf(n: int) -> int:
    if n < 0:
        raise make_error()
    return n + 1

def observer() -> int:
    sys.setrecursionlimit(1000)
    return 17

def partial(n: int) -> int:
    if n == 0:
        return observer()
    return cold_leaf(n)

print(partial(2))
'''


class TypedRecursionPartialTests(unittest.TestCase):
    def test_cold_child_publishes_both_source_frames(self):
        ir, functions = compile_source(PARTIAL)
        root = functions["@rp.f.partial"]
        child = functions["@rp2.f.cold_leaf"]
        self.assertTrue(any(op[:2] == ("call", "@rp2.f.cold_leaf") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("call", "@f.observer") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("call", "@f.make_error") for op in operations(child)))
        self.assertFalse(any(op[:2] in [("rt", "recursion.check"), ("rt", "recursion.enter")]
                             for op in operations(child)))
        additions = [child["operands"][(label, at)][0]
                     for label, _, code in child["blocks"] for at, op in enumerate(code)
                     if op[:2] == ("scalar.bin", "add")]
        self.assertTrue(any(values[1:] == ["2"] for values in additions))
        declaration = next(line for line in ir.splitlines()
                           if line.startswith("define ") and "@rp.f.partial(" in line)
        self.assertIn("alwaysinline", declaration)
        child_declaration = next(line for line in ir.splitlines()
                                 if line.startswith("define ") and "@rp2.f.cold_leaf(" in line)
        self.assertIn("alwaysinline", child_declaration)

    def test_original_fallback_retains_all_source_entry_guards(self):
        _, functions = compile_source(PARTIAL)
        root = functions["@f.partial"]
        self.assertTrue(any(op[:2] == ("rt", "recursion.room") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("rt", "recursion.enter") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("call", "@f.cold_leaf") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("call", "@f.observer") for op in operations(root)))
        self.assertTrue(any(op[:2] == ("rt", "recursion.check")
                            for op in operations(functions["@f.cold_leaf"])))

    def test_cold_publication_is_required_exactly_once(self):
        original = Gen.recursionregion
        for change in ("remove", "duplicate"):
            def mutate(g, selected=change):
                for fn in g.fns:
                    if fn.f.name != "cold_leaf":
                        continue
                    for block in fn.blocks:
                        changed = []
                        for op in block.code:
                            if op.op == "rt" and op.s == "recursion.enter":
                                if selected == "remove":
                                    continue
                                extra = recursion_copy(op)
                                fn.n += 1
                                extra.r = [fn.n]
                                changed.append(extra)
                            changed.append(op)
                        block.code = changed
                return original(g)

            with self.subTest(change=change), patch.object(Gen, "recursionregion", mutate):
                _, functions = compile_source(PARTIAL)
            self.assertNotIn("@rp.f.partial", functions)
            self.assertNotIn("@rp2.f.cold_leaf", functions)

    def test_suffix_calls_stay_guarded_after_limit_mutation(self):
        _, functions = compile_source('''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer() -> None:
    sys.setrecursionlimit(1000)

def partial(n: int) -> int:
    if n < 0:
        observer()
        leaf(n)
        raise ValueError("done")
    return leaf(n)

print(partial(2))
''')
        code = operations(functions["@rp.f.partial"])
        self.assertTrue(any(op[:2] == ("call", "@rp2.f.leaf") for op in code))
        self.assertTrue(any(op[:2] == ("call", "@f.leaf") for op in code))
        self.assertTrue(any(op[:2] == ("call", "@f.observer") for op in code))

    def test_observer_followed_by_unchecked_returning_work_is_excluded(self):
        _, functions = compile_source('''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer() -> int:
    sys.setrecursionlimit(1000)
    return 3

def partial(n: int) -> int:
    if n == 0:
        value = observer()
        return leaf(value)
    return leaf(n)

print(partial(2))
''')
        self.assertNotIn("@rp.f.partial", functions)

    def test_aggregate_root_keeps_tuple_return_optimization(self):
        ir, functions = compile_source('''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer(n: int) -> int:
    sys.setrecursionlimit(1000)
    return n

def partial(n: int) -> tuple[int, int]:
    if n < 0:
        value = observer(n)
        return (value, n)
    return (leaf(n), n)

def unpack(n: int) -> int:
    left, right = partial(n)
    return left + right

print(unpack(2))
''')
        self.assertNotIn("@rp.f.partial", functions)
        self.assertIn("@v.f.partial(", ir)

    def test_oversized_partial_root_is_not_forced_inline(self):
        body = "\n".join("    n += 1" for _ in range(200))
        source = PARTIAL.replace("    if n == 0:\n        return observer()",
                                 body + "\n    if n == 0:\n        return observer()")
        _, functions = compile_source(source)
        self.assertNotIn("@rp.f.partial", functions)

    def test_prefix_child_before_dispatch_does_not_justify_versioning(self):
        _, functions = compile_source('''
import sys

def leaf(n: int) -> int:
    return n + 1

def observer(n: int) -> int:
    sys.setrecursionlimit(1000)
    return n

def partial(n: int) -> int:
    value = leaf(n)
    if n == 0:
        return value
    return observer(value)

print(partial(2))
''')
        self.assertNotIn("@rp.f.partial", functions)

    def test_inline_budget_charges_every_child_callsite(self):
        child_body = "\n".join("    n += 1" for _ in range(24))
        root_body = "\n".join("    n = leaf(n)" for _ in range(24))
        source = '''
import sys

def leaf(n: int) -> int:
CHILD
    return n

def observer(n: int) -> int:
    sys.setrecursionlimit(1000)
    return n

def partial(n: int) -> int:
    if n < 0:
        return observer(n)
ROOT
    return leaf(n)

print(partial(2))
'''.replace("CHILD", child_body)
        _, one_call = compile_source(source.replace("ROOT", ""))
        self.assertIn("@rp.f.partial", one_call)
        _, repeated = compile_source(source.replace("ROOT", root_body))
        self.assertNotIn("@rp.f.partial", set(repeated))

    def test_partial_scalar_identity_fixture_uses_hidden_argument_and_return_abi(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "tests/programs/inference/dynany_recursion_bounded.py").read_text()
        ir, functions = compile_source(source)
        wrapper = functions["@f.partial_identity"]
        fast = functions["@rp.f.partial_identity"]
        self.assertIn("@rp2.f.identity", functions)
        self.assertTrue(any(op[:2] == ("call", "@rp2.f.identity") for op in operations(fast)))
        self.assertTrue(any(op[:2] == ("call", "@f.identity_observer") for op in operations(fast)))
        arguments = [wrapper["operands"][(label, at)][0]
                     for label, _, code in wrapper["blocks"] for at, op in enumerate(code)
                     if op[:2] == ("call", "@rp.f.partial_identity")]
        self.assertEqual(len(arguments), 1)
        self.assertEqual(arguments[0][-2:], ["%aid0", "%idret"])
        for symbol in ("@rp.f.partial_identity", "@rp2.f.identity"):
            declaration = next(line for line in ir.splitlines()
                               if line.startswith("define ") and symbol + "(" in line)
            self.assertIn("{i64, ptr} %a0", declaration)
            self.assertIn("ptr %aid0, ptr %idret", declaration)


if __name__ == "__main__":
    unittest.main()
