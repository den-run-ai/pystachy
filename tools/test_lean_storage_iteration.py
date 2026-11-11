"""Guard controls for variable-index tuple digit reads in real compiled IR."""
from __future__ import annotations

import copy
import os
import unittest

import check_lean_boundary as boundary
import check_lean_storage as storage
from test_lean_int import compile_snapshot


ORDINARY = """# pystachy: python-int
def fold(t: tuple[int, int]) -> int:
    total = 0
    for value in t:
        total += value
    return total

print(fold((2 ** 70, 2 ** 80)))
"""

OPTIONAL = """# pystachy: python-int
def fold(t: tuple[int, int] | None) -> int:
    total = 0
    if t is not None:
        for value in t:
            total += value
    return total

print(fold((10, 20)), fold(None))
"""

CHANGING = """# pystachy: python-int
def produced(index: int) -> tuple[int, int]:
    return index, 2 ** 70 + index

def fold() -> int:
    total = 0
    for index in range(3):
        pair = produced(index)
        total += pair[0] + pair[1]
    return total

print(fold())
"""


def operations(fn):
    return [op for block in fn["blocks"] for op in block["operations"]]


def marker_branches(fn):
    definitions = {f"%t{number}": op for op in operations(fn) for number in op["results"]}
    found = []
    for op in operations(fn):
        if op["op"] != "cbr":
            continue
        condition = definitions.get(storage.args(op)[0])
        if condition and condition["op"] == "scalar.cmp" and condition["text"] == "eq" \
                and storage.MIN in storage.args(condition):
            found.append(op)
    return found


if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not storage.DEFAULT_CHECKER.is_file():
    raise RuntimeError("Lean tuple-iteration checks require the built boundary executable")


class TupleIterationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.functions = {}
        for name, source in (("ordinary", ORDINARY), ("optional", OPTIONAL), ("changing", CHANGING)):
            snapshot = compile_snapshot(source)
            cls.functions[name] = next(fn for fn in snapshot["functions"] if fn["symbol"] == "@f.fold")

    def test_each_iteration_inventories_its_machine_tail_read(self):
        fn = self.functions["ordinary"]
        self.assertTrue(any(op["op"] == "mach.load" for op in operations(fn)))
        _, metadata = storage.Normalize(fn).build()
        self.assertGreater(metadata["tail_reads"], 0)
        self.assertTrue(any(site["kind"] == "dynamic-tail-marker" for site in metadata["sites"]))

    def test_plain_optional_iteration_does_not_invent_digit_slots(self):
        # Optional tuple annotations retain 64-bit items. Its two machine loads
        # read the loop counter and the item, not an item and a digit pointer.
        fn = self.functions["optional"]
        self.assertEqual(fn["parameters"][0]["representation"], "opt[tuple[int,int]]")
        self.assertEqual(len([op for op in operations(fn) if op["op"] == "mach.load"]), 2)
        self.assertEqual(marker_branches(fn), [])
        _, metadata = storage.Normalize(fn).build()
        self.assertEqual(metadata["tail_reads"], 0)

    def test_unknown_dynamic_tail_offset_is_unsupported(self):
        for name, original in [("ordinary", self.functions["ordinary"])]:
            with self.subTest(layout=name):
                fn = copy.deepcopy(original)
                normalized = storage.Normalize(fn)
                tails = []
                for op in operations(fn):
                    machine = normalized.machine_tuple(op)
                    if machine is None:
                        continue
                    _, index, typ = machine
                    offset = normalized.defs.get(index)
                    if offset and offset["op"] == "scalar.bin" and offset["text"] == "add" \
                            and storage.args(offset)[1] == str(len(storage.targs(typ))):
                        tails.append(offset)
                self.assertEqual(len(tails), 1, "control must mutate the actual trailing address")
                tails[0]["operands"][1]["value"] = str(int(storage.args(tails[0])[1]) + 1)
                with self.assertRaises(storage.Unsupported):
                    storage.Normalize(fn).build()

    @unittest.skipUnless(storage.DEFAULT_CHECKER.is_file(), "build the Lean checker")
    def test_removed_marker_guards_reject_without_losing_tail_obligation(self):
        for name, original in [("ordinary", self.functions["ordinary"])]:
            with self.subTest(layout=name):
                candidate, metadata = storage.Normalize(original).build()
                self.assertTrue(boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata))
                guards = marker_branches(original)
                self.assertTrue(guards, "control must find the loop's actual marker guard")
                for index in range(len(guards)):
                    fn = copy.deepcopy(original)
                    marker_branches(fn)[index]["operands"][0]["value"] = "true"
                    corrupt, details = storage.Normalize(fn).build()
                    self.assertEqual(details["tail_reads"], metadata["tail_reads"])
                    self.assertTrue(any(site["kind"] == "dynamic-tail-marker" for site in details["sites"]))
                    self.assertFalse(boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(corrupt), details))

    @unittest.skipUnless(storage.DEFAULT_CHECKER.is_file(), "build the Lean checker")
    def test_new_tuple_each_iteration_still_requires_each_marker_guard(self):
        original = self.functions["changing"]
        self.assertTrue(any(op["op"] == "call" and op["type"] == "tuple[int+,int+]"
                            for op in operations(original)))
        candidate, metadata = storage.Normalize(original).build()
        self.assertGreater(metadata["tail_reads"], 0)
        self.assertTrue(boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata))
        guards = marker_branches(original)
        self.assertEqual(len(guards), 2)
        for index in range(len(guards)):
            with self.subTest(item=index):
                fn = copy.deepcopy(original)
                marker_branches(fn)[index]["operands"][0]["value"] = "true"
                corrupt, details = storage.Normalize(fn).build()
                self.assertEqual(details["tail_reads"], metadata["tail_reads"])
                self.assertFalse(boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(corrupt), details))


if __name__ == "__main__":
    unittest.main()
