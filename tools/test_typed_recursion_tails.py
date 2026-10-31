"""Share only equivalent terminal calls in an already-proven private region."""
from pathlib import Path
import unittest
from unittest.mock import patch

from test_typed_recursion import compile_source, operations
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.optimizations import recursion_merge_tails
from src.pystachy_compiler.syntax import Node


def ins(op, t="", s="", args=(), results=(), labels=()):
    item = Ins(op, t, s)
    item.a = [Val(value, typ) for value, typ in args]
    item.r = list(results)
    item.b = list(labels)
    return item


def duplicate_tails():
    fn = IFn(FnInfo("partial", "@rp.f.partial", Node("def", "partial", 1), ""))
    fn.n = 30
    fn.f.ret = "int"
    fn.slots = [ins("slot", "int", "arg", results=[1])]
    fn.blocks[0].code = [ins("cbr", args=[("%a0", "bool")], labels=["L10", "L20"])]
    for label, number in [("L10", 2), ("L20", 4)]:
        block = Blk(label)
        block.code = [ins("mem.load", "int", args=[("%arg.1", "*int")], results=[number]),
                      ins("call", "int", "@rp2.f.leaf", args=[(f"%t{number}", "int")], results=[number + 1]),
                      ins("ret", args=[(f"%t{number + 1}", "int")])]
        fn.blocks.append(block)
    return fn


class TerminalShapeTests(unittest.TestCase):
    def test_equivalent_returns_share_one_call_without_moving_prefix_stores(self):
        fn = duplicate_tails()
        prefixes = []
        for index, target in enumerate(["L10", "L20"]):
            block = Blk("left" if index == 0 else "right")
            block.code = [ins("mem.store", args=[("%arg.1", "*int"), (str(index + 1), "int")]),
                          ins("br", labels=[target])]
            prefixes.append(block)
        fn.blocks[0].code[0].b = ["left", "right"]
        fn.blocks[1:1] = prefixes
        self.assertEqual(recursion_merge_tails(fn), 1)
        self.assertEqual(fn.blocks[0].code[0].b, ["left", "right"])
        self.assertEqual([block.code[0].a[1].v for block in prefixes], ["1", "2"])
        self.assertEqual([block.code[-1].b for block in prefixes], [["L10"], ["L10"]])
        self.assertEqual(sum(op.op == "call" for block in fn.blocks for op in block.code), 1)

    def test_different_slots_or_hidden_identity_arguments_do_not_merge(self):
        for difference in ("slot", "identity", "return_identity", "callee", "type", "k", "x"):
            with self.subTest(difference=difference):
                fn = duplicate_tails()
                left, right = fn.blocks[1].code, fn.blocks[2].code
                if difference == "slot":
                    fn.slots.append(ins("slot", "int", "other", results=[6]))
                    right[0].a[0] = Val("%other.6", "*int")
                elif difference in ("identity", "return_identity"):
                    typ = "dyn" if difference == "identity" else "*dyn"
                    left[1].a.append(Val("%identity0", typ))
                    right[1].a.append(Val("%identity1", typ))
                elif difference == "callee":
                    right[1].s = "@rp2.f.other"
                elif difference == "type":
                    right[1].a[0].t = "float"
                elif difference == "k":
                    right[1].k = 1
                else:
                    right[1].x = "different"
                self.assertEqual(recursion_merge_tails(fn), 0)
                self.assertEqual(fn.blocks[0].code[0].b, ["L10", "L20"])

    def test_side_effects_and_publication_inside_a_tail_are_not_removed(self):
        for op in (ins("mem.store", args=[("%arg.1", "*int"), ("8", "int")]),
                   ins("rt", "None", "recursion.restore", args=[("%active", "int")])):
            with self.subTest(op=op.op):
                fn = duplicate_tails()
                fn.blocks[2].code.insert(0, op)
                self.assertEqual(recursion_merge_tails(fn), 0)
                self.assertIs(fn.blocks[2].code[0], op)

    def test_external_result_uses_and_nonordinary_label_references_block_sharing(self):
        for reference in ("use", "phi_value", "phi_label", "cold", "cold_handler", "handler", "check", "metadata"):
            with self.subTest(reference=reference):
                fn = duplicate_tails()
                extra = Blk("extra")
                extra.code = [ins("ret", args=[("0", "int")])]
                fn.blocks.append(extra)
                if reference == "use":
                    extra.code[0].a[0] = Val("%t5", "int")
                elif reference.startswith("phi"):
                    extra.code.insert(0, ins("phi", "int", args=[("%t5" if reference == "phi_value" else "0", "int")],
                                             results=[6], labels=["L20" if reference == "phi_label" else "entry"]))
                elif reference == "cold":
                    fn.cold["error"] = "L20"
                elif reference == "cold_handler":
                    fn.coldh["error"] = "L20"
                elif reference == "handler":
                    extra.handler = "L20"
                elif reference == "check":
                    extra.code = [ins("check", s="error", args=[("true", "bool")], labels=["L20"])]
                else:
                    fn.fa["%t5"] = True
                self.assertEqual(recursion_merge_tails(fn), 0)

    def test_public_functions_and_the_first_block_are_never_merged(self):
        fn = duplicate_tails()
        fn.f.ll = "@f.partial"
        self.assertEqual(recursion_merge_tails(fn), 0)
        fn = duplicate_tails()
        fn.blocks = fn.blocks[1:]
        self.assertEqual(fn.blocks[0].label, "L10")
        self.assertEqual(recursion_merge_tails(fn), 0)


DUPLICATE_METHOD = '''
import sys

def make_error() -> ValueError:
    return ValueError("cold")

def observer() -> int:
    sys.setrecursionlimit(1000)
    return 17

class Reader:
    def __init__(self, value: int):
        self.value = value

    def child(self) -> int:
        if self.value < 0:
            raise make_error()
        return self.value + 1

    def choose(self, mode: int) -> int:
        if mode == 0:
            return observer()
        if mode == 1:
            return self.child()
        return self.child()

print(Reader(2).choose(1))
'''


class TerminalCompilationTests(unittest.TestCase):
    def test_only_the_private_body_changes_and_its_cold_publication_stays(self):
        _, merged = compile_source(DUPLICATE_METHOD)
        with patch("src.pystachy_compiler.optimizations.recursion_merge_tails", return_value=0):
            _, original = compile_source(DUPLICATE_METHOD)
        root, child = "@rp.m.Reader.choose", "@rp2.m.Reader.child"
        self.assertEqual(set(merged), set(original))
        self.assertEqual(sum(op[:2] == ("call", child) for op in operations(merged[root])), 1)
        self.assertEqual(sum(op[:2] == ("call", child) for op in operations(original[root])), 2)
        for name in merged:
            if name != root:
                self.assertEqual(merged[name], original[name], name)
        self.assertTrue(any(op[:2] == ("rt", "recursion.restore") for op in operations(merged[child])))
        self.assertIn(("call", "@f.observer"), [op[:2] for op in operations(merged[root])])

    def test_calibrated_low_limit_paths_keep_the_offset_two_bridge(self):
        root = Path(__file__).resolve().parent.parent
        source = (root / "tests/programs/language/recursion_partial_tails.py").read_text()
        _, functions = compile_source(source)
        fast = functions["@rp.f.partial"]
        child = functions["@rp2.f.cold_leaf"]
        self.assertEqual(sum(op[:2] == ("call", "@rp2.f.cold_leaf") for op in operations(fast)), 1)
        self.assertEqual(sum(op[:2] == ("call", "@f.cold_leaf") for op in operations(functions["@f.partial"])), 2)
        additions = [child["operands"][(label, at)][0]
                     for label, _, code in child["blocks"] for at, op in enumerate(code)
                     if op[:2] == ("scalar.bin", "add")]
        self.assertTrue(any(values[1:] == ["2"] for values in additions))


if __name__ == "__main__":
    unittest.main()
