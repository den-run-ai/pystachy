"""Complete stack-tuple transport must retain its exact source and extent guard."""
from __future__ import annotations

import copy
import unittest

import check_lean_boundary as boundary
import check_lean_storage as storage
from test_lean_int import compile_snapshot


SOURCE = """# pystachy: python-int
def pack(*args):
    return args

print(pack(2 ** 70, 2 ** 80))
"""


def operations(fn):
    return [op for block in fn["blocks"] for op in block["operations"]]


@unittest.skipUnless(storage.DEFAULT_CHECKER.is_file(), "build the Lean checker")
class StackCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot = compile_snapshot(SOURCE)
        cls.original = next(fn for fn in snapshot["functions"] if fn["name"] == "pack")

    def accepted(self, fn):
        candidate, metadata = storage.Normalize(fn).build()
        self.assertEqual(metadata["stack_copy_reads"], 4)
        self.assertEqual(metadata["stack_copy_obligations"], 2)
        self.assertEqual(metadata["tail_reads"], 0)
        return boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata)

    def test_complete_same_layout_copy_is_checked(self):
        self.assertTrue(self.accepted(self.original))

    def test_stack_test_cannot_be_bypassed_or_test_another_pointer(self):
        for mutation in ("bypass", "wrong source"):
            with self.subTest(mutation=mutation):
                fn = copy.deepcopy(self.original)
                ops = operations(fn)
                call = next(op for op in ops if op["op"] == "rt" and op["text"] == "on_stack")
                if mutation == "wrong source":
                    call["operands"][0]["value"] = "%a0"
                else:
                    comparison = next(op for op in ops if op["op"] == "num.cmp" and
                                      storage.result(call) in storage.args(op))
                    branch = next(op for op in ops if op["op"] == "cbr" and
                                  storage.args(op) == [storage.result(comparison)])
                    branch["operands"][0]["value"] = "true"
                self.assertFalse(self.accepted(fn))

    def test_partial_reordered_or_different_layout_copy_is_unsupported(self):
        for mutation in ("missing word", "wrong index", "outside extent", "different layout",
                         "changed word", "extra use", "all stores removed", "computed index", "copy branches"):
            with self.subTest(mutation=mutation):
                fn = copy.deepcopy(self.original)
                normalized = storage.Normalize(fn)
                self.assertEqual(len(normalized.stack_copy_stores), 4)
                target = next(block for block in fn["blocks"] if any(
                    id(op) in normalized.stack_copy_stores for op in block["operations"]))
                copied = target["operations"]
                store = next(op for op in copied if id(op) in normalized.stack_copy_stores)
                address = normalized.defs[storage.args(store)[0]]
                load = normalized.defs[storage.args(store)[1]]
                if mutation == "missing word":
                    copied.remove(store)
                elif mutation == "wrong index":
                    address["operands"][1]["value"] = "1"
                elif mutation == "outside extent":
                    normalized.defs[storage.args(load)[0]]["operands"][1]["value"] = "4"
                elif mutation == "different layout":
                    allocation = normalized.defs[storage.args(address)[0]]
                    allocation["type"] = "tuple[int,int]"
                elif mutation == "changed word":
                    store["operands"][1]["value"] = "0"
                elif mutation == "all stores removed":
                    target["operations"] = [op for op in copied if id(op) not in normalized.stack_copy_stores]
                elif mutation == "computed index":
                    from test_lean_storage import ins
                    source_address = normalized.defs[storage.args(load)[0]]
                    number = max(number for op in operations(fn) for number in op["results"]) + 1
                    copied.insert(copied.index(source_address), ins("scalar.bin", "int",
                        [("0", "int"), ("2", "int")], number, "add"))
                    source_address["operands"][1]["value"] = f"%t{number}"
                    target["operations"] = [op for op in copied if id(op) not in normalized.stack_copy_stores]
                elif mutation == "copy branches":
                    load["targets"] = [target["label"], target["label"]]
                else:
                    from test_lean_storage import ins
                    copied.insert(copied.index(store) + 1, ins("rt", "None",
                        [(storage.result(load), "int")], text="print.int"))
                with self.assertRaises(storage.Unsupported):
                    storage.Normalize(fn).build()


if __name__ == "__main__":
    unittest.main()
