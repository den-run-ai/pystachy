"""Decoding a promoting int container's raw slot word (gen_big_slot): the word is the int only
where it is not the marker, else the container's digits give it. Each control breaks the
decode as a compiler bug could; Lean must reject it, or the adapter refuse it."""
from __future__ import annotations

import copy
import os
import unittest

import check_lean_boundary as boundary
import check_lean_storage as storage
from test_lean_storage import block, function, ins

LIST = "list[int]"
SET = "set[int]"


def decode(container=LIST, read=("list.load", ""), helper="list.big_at", test=("eq", storage.MIN)):
    """entry reads the word, makes it the int (speculatively) and tests it for the marker; rare
    takes the digits; end joins the two ints."""
    op, text = read
    word = (ins(op, "*int", [("%a0", container), ("%a1", "int")], 1, text) if op == "list.load"
            else ins("rt", "*int", [("%a0", container), ("%a1", "int")], 1, text))
    rare = [ins("rt", "%ptr", [("%a0", container), ("%a1", "int")], 4, helper),
            ins("scalar.cast", "int", [("%t4", "%ptr")], 5, "ptrtoint"),
            ins("scalar.cmp", "bool", [("%t5", "int"), ("0", "int")], 6, "eq"),
            ins("select", "int", [("%t6", "bool"), ("%t1" if container == SET else storage.MIN, "int"), ("0", "int")], 7),
            ins("scalar.cast", "%ptr", [("%t5", "int")], 8, "inttoptr"),
            ins("big.make", "int+", [("%t7", "int"), ("%t8", "%ptr")], 9),
            ins("br", targets=["end"])]
    return function([
        block("entry", word,
              ins("big.make", "int+", [("%t1", "int"), ("null", "%ptr")], 2),
              ins("scalar.cmp", "bool", [("%t1", "int"), (test[1], "int")], 3, test[0]),
              ins("cbr", operands=[("%t3", "bool")], targets=["rare", "end"])),
        block("rare", *rare),
        block("end", ins("phi", "int+", [("%t2", "int+"), ("%t9", "int+")], 10, targets=["entry", "rare"]),
              ins("ret.none")),
    ], parameters=(container, "int"))


if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not storage.DEFAULT_CHECKER.is_file():
    raise RuntimeError("Lean storage checks require the built boundary executable")


@unittest.skipUnless(storage.DEFAULT_CHECKER.is_file(), "build the Lean checker")
class ContainerDecodeTests(unittest.TestCase):
    def accepted(self, fn):
        candidate, metadata = storage.Normalize(fn).build()
        kinds = [site["kind"] for site in metadata["sites"]]
        self.assertIn("container-decode", kinds, "control must exercise a decode obligation")
        return boundary.run_checker(storage.DEFAULT_CHECKER, boundary.encode(candidate), metadata)

    def test_each_container_decode_is_proved(self):
        for fn in (decode(), decode(read=("rt", "list.get")), decode("dict[str,int]", ("rt", "dict.val"), "dict.big_val"),
                   decode("dict[int,str]", ("rt", "dict.key"), "dict.big_key"),
                   decode(SET, ("rt", "set.key"), "set.big_key", ("sle", storage.SET_SENTINEL))):
            with self.subTest(read=fn["blocks"][0]["operations"][0]["text"] or "list.load"):
                self.assertTrue(self.accepted(fn))

    def test_untested_word_is_rejected(self):
        # (the marker test made opaque: a large item would read as -2**63)
        for fn in (decode(), decode(SET, ("rt", "set.key"), "set.big_key", ("sle", storage.SET_SENTINEL))):
            ops = fn["blocks"][0]["operations"]
            ops[2] = ins("scalar.cmp", "bool", [("1", "int"), ("1", "int")], 3, "eq")
            self.assertFalse(self.accepted(fn))

    def test_fast_path_on_the_marker_edge_is_rejected(self):
        fn = decode()
        fn["blocks"][0]["operations"][-1]["targets"] = ["end", "rare"]
        self.assertFalse(self.accepted(fn))

    def test_marker_test_of_another_word_is_rejected(self):
        # (the test reads the next item, not the decoded one)
        fn = decode()
        ops = fn["blocks"][0]["operations"]
        ops.insert(1, ins("list.load", "*int", [("%a0", LIST), ("1", "int")], 11))
        ops[3]["operands"][0]["value"] = "%t11"
        ops.insert(4, ins("big.make", "int+", [("%t11", "int"), ("null", "%ptr")], 12))
        self.assertFalse(self.accepted(fn))

    def test_word_used_outside_its_decode_is_unsupported(self):
        fn = decode()
        fn["blocks"][2]["operations"].insert(0, ins("scalar.bin", "int", [("%t1", "int"), ("1", "int")], 20, "add"))
        with self.assertRaisesRegex(storage.Unsupported, "outside its decode"):
            storage.Normalize(fn).build()
        fn = decode()
        fn["blocks"][0]["operations"].insert(2, ins("big.lo", "int", [("%t2", "int+")], 21))
        with self.assertRaisesRegex(storage.Unsupported, "before its marker test"):
            storage.Normalize(fn).build()

    def test_plain_containers_hold_no_promoting_words(self):
        fn = decode()
        fn["representation_metadata"]["int_containers"] = False
        candidate, metadata = storage.Normalize(copy.deepcopy(fn)).build()
        self.assertNotIn("container-decode", [site["kind"] for site in metadata["sites"]])


if __name__ == "__main__":
    unittest.main()
