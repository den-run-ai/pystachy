"""Guarded callback versions must expose direct calls without freezing mutable bindings."""
from copy import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.utils import identity_abi


ROOT = Path(__file__).resolve().parent.parent
KERNEL = """
from collections.abc import Callable

def kernel(callback: Callable[[int], int], values: list[int]) -> int:
    total = 0
    for value in values:
        total += callback(value)
    return total
"""
TARGETS = """
def square(value: int) -> int:
    return value * value

first: list[Callable[[int], int]] = [square]
print(kernel(first[0], [2, 3]))

def negative(value: int) -> int:
    return -value

later: list[Callable[[int], int]] = [negative]
print(kernel(later[0], [2, 3]))
"""


def compile_source(source, opt=""):
    captured = {}
    lower = Gen.lower

    def capture(gen, fn):
        # program() releases these lists after lowering; retain the pre-lowering IR.
        captured[fn.f.ll] = copy(fn)
        lower(gen, fn)

    with patch.object(Gen, "lower", capture), patch.dict(os.environ, {
            "PYSTACHY_IRCHECK": "1", "PYSTACHY_IRFX": "0", "PYSTACHY_OPT": opt}):
        gen = Gen()
        ir = gen.program(Loader([]).program("callback_contract.py", source))
    return gen, captured, ir


def operations(fn):
    return [op for block in fn.blocks for op in block.code]


def versions(functions, name="kernel"):
    return [fn for symbol, fn in functions.items() if fn.f.name == name and ".callback" in symbol]


def target_guards(fn):
    return [(block, op) for block in fn.blocks for op in block.code
            if op.op == "ptr.cmp" and any(a.v.startswith("@cvo.") for a in op.a)]


class CallbackSpecializationTests(unittest.TestCase):
    def test_two_entry_guards_keep_fallback_and_call_the_matching_adapters(self):
        # The kernel is first compiled before negative/third acquire adapters.
        # Discovery must see the completed program, but keep only two versions.
        source = KERNEL + TARGETS + """
def third(value: int) -> int:
    return value + 100

last: list[Callable[[int], int]] = [third]
print(kernel(last[0], [2, 3]))
"""
        gen, functions, _ = compile_source(source)
        kernel = functions["@f.kernel"]
        variants = versions(functions)
        self.assertEqual(len(variants), 2)
        adapters = {name: gen.adapters[f"fn[f:{name}] callable[int,int]"]
                    for name in ("square", "negative", "third")}
        guards = target_guards(kernel)
        self.assertEqual(len(guards), 2)
        self.assertEqual([op.a[1].v for _, op in guards],
                         ["@cvo." + adapters[name][4:] for name in ("square", "negative")])
        self.assertEqual(sum(op.op == "icall" for op in operations(kernel)), 1)
        blocks = {block.label: block for block in kernel.blocks}
        self.assertEqual(guards[0][0].label, "entry")
        for (block, guard), variant in zip(guards, variants):
            self.assertEqual(guard.s, "==")
            self.assertEqual(guard.a[0].v, "%a0")
            branch = block.code[-1]
            self.assertEqual((branch.op, branch.a[0].v), ("cbr", f"%t{guard.r[0]}"))
            hit = blocks[branch.b[0]]
            self.assertEqual([op.s for op in hit.code if op.op == "call"], [variant.f.ll])
            direct = [op for op in operations(variant)
                      if op.op == "call" and op.s in gen.adapters.values()]
            self.assertEqual(len(direct), 1)
            self.assertEqual("@cvo." + direct[0].s[4:], guard.a[1].v)
            self.assertEqual(direct[0].a[0].v, "null")
            self.assertEqual([a.t for a in direct[0].a], functions[direct[0].s].f.ptypes)
            self.assertFalse(any(op.op == "icall" for op in operations(variant)))
            self.assertEqual(variant.f.ret, "int")
        self.assertEqual(guards[0][0].code[-1].b[1], guards[1][0].label)
        pending, seen, fallback = [guards[-1][0].code[-1].b[1]], set(), []
        while pending:
            label = pending.pop()
            if label not in seen:
                seen.add(label)
                fallback.extend(blocks[label].code)
                pending.extend(blocks[label].code[-1].b)
        self.assertTrue(any(op.op == "icall" for op in fallback))
        # The only predecessors of the dispatch blocks are earlier dispatch blocks:
        # returning to the loop header cannot repeat a target test per element.
        labels = {block.label for block, _ in guards}
        for block in kernel.blocks:
            for destination in block.code[-1].b:
                if destination in labels:
                    self.assertIn(block.label, labels)

    def test_disabling_the_pass_is_an_indirect_call_control(self):
        for opt in ("-callbacks", "-all"):
            with self.subTest(opt=opt):
                _, functions, _ = compile_source(KERNEL + TARGETS, opt)
                self.assertEqual(versions(functions), [])
                kernel = functions["@f.kernel"]
                self.assertEqual(target_guards(kernel), [])
                self.assertEqual(sum(op.op == "icall" for op in operations(kernel)), 1)

    def test_reassigned_or_captured_callback_slots_are_not_specialized(self):
        path = ROOT / "tests/programs/language/guarded_callback_writes.py"
        _, functions, _ = compile_source(path.read_text() + """
def captured(callback: Callable[[int], int], values: list[int]) -> int:
    def read(value: int) -> int:
        return callback(value)
    total = 0
    for value in values:
        total += callback(value) + read(value)
    return total

print(captured(callbacks[0], [2, 3]))
""")
        for name in ("local_write", "cell_write", "argument_write", "captured"):
            with self.subTest(name=name):
                self.assertEqual(versions(functions, name), [])
                self.assertTrue(any(op.op == "icall" for op in operations(functions[f"@f.{name}"])))

    def test_try_generator_and_dynamic_identity_abi_remain_generic(self):
        source = KERNEL + TARGETS + """
def handled(callback: Callable[[int], int], values: list[int]) -> int:
    total = 0
    try:
        for value in values:
            total += callback(value)
    except ValueError:
        return -1
    return total

def generated(callback: Callable[[int], int], values: list[int]):
    for value in values:
        yield callback(value)

print(handled(first[0], [2, 3]), list(generated(first[0], [2, 3])))
"""
        _, functions, _ = compile_source(source)
        self.assertEqual(len(versions(functions)), 2)  # same-program positive control
        for name in ("handled", "generated"):
            with self.subTest(name=name):
                self.assertEqual(versions(functions, name), [])
                original = [fn for fn in functions.values() if fn.f.name == name]
                self.assertEqual(len(original), 1)
                self.assertTrue(any(op.op == "icall" for op in operations(original[0])))
        _, dynamic, _ = compile_source("# pystachy: dynamic-any\n" + KERNEL + TARGETS)
        self.assertTrue(identity_abi(dynamic["@f.kernel"].f))
        self.assertEqual(versions(dynamic), [])
        self.assertTrue(any(op.op == "icall" for op in operations(dynamic["@f.kernel"])))

    def test_callback_only_in_loop_else_is_not_a_repeated_call(self):
        _, functions, _ = compile_source("""
from collections.abc import Callable

def square(value: int) -> int:
    return value * value

def kernel(callback: Callable[[int], int], values: list[int]) -> int:
    total = 0
    for value in values:
        total += value
    else:
        total = callback(total)
    return total

kernel(square, [2, 3])
""")
        self.assertEqual(versions(functions), [])
        self.assertTrue(any(op.op == "icall" for op in operations(functions["@f.kernel"])))

    def test_only_the_original_kernel_counts_a_recursion_frame(self):
        path = ROOT / "tests/programs/language/guarded_callback_recursion.py"
        _, functions, _ = compile_source(path.read_text())
        kernel = functions["@f.kernel"]
        self.assertTrue(kernel.counted)
        self.assertTrue(functions["@f.step"].counted)
        self.assertEqual(sum(op.op == "rt" and op.s == "recursion.enter"
                             for op in operations(kernel)), 1)
        for block in kernel.blocks:
            if block.code[-1].op in ("ret", "ret.none"):
                self.assertEqual((block.code[-2].op, block.code[-2].s), ("rt", "recursion.restore"))
        variants = versions(functions)
        self.assertEqual(len(variants), 1)
        self.assertFalse(variants[0].counted)
        self.assertFalse(any(op.op == "rt" and op.s in ("recursion.enter", "recursion.restore")
                             for op in operations(variants[0])))

    def test_void_kernel_and_effectful_target_get_versions(self):
        _, functions, _ = compile_source("""
from collections.abc import Callable

def observe(value: int) -> None:
    print(value)

def kernel(callback: Callable[[int], None], values: list[int]) -> None:
    for value in values:
        callback(value)

kernel(observe, [2, 3])
""")
        variants = versions(functions)
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].f.ret, "None")
        kernel = functions["@f.kernel"]
        calls = [op for op in operations(kernel) if op.op == "call" and op.s == variants[0].f.ll]
        self.assertEqual(len(calls), 1)
        self.assertEqual((calls[0].t, calls[0].r), ("None", []))
        path = ROOT / "tests/programs/language/guarded_callback_effects.py"
        gen, functions, _ = compile_source(path.read_text())
        variants = versions(functions, "apply")
        self.assertEqual(len(variants), 1)
        adapter = gen.adapters["fn[f:observe] callable[int,int]"]
        self.assertTrue(any(op.op == "call" and op.s == adapter for op in operations(variants[0])))


if __name__ == "__main__":
    unittest.main()
