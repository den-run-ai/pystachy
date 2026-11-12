"""Layout reads become machine ops before a function is printed, with the same LLVM.

legacy() holds the text that lowering.py printed for each layout read before the machine
stage existed: the stage and the machine printer together must still give it.
"""
from contextlib import redirect_stderr
from io import StringIO
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.ircheck import RESULT_NUMBERS
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.machine_ir import WORD_READS, machine_ops
from src.pystachy_compiler.specs import IROPS
from src.pystachy_compiler.syntax import Node

READS = {
    "list.len": ("int", "list[int]", ""),
    "union.tag": ("int", "union[int,float]", ""),
    "dyn.type": ("dyntype", "dyn", ""),
    "union.payload": ("%slot", "union[int,float]", "int"),
    "union.raw": ("%slot", "union[int,float]", ""),
    "dyn.payload": ("%slot", "dyn", "int"),
    "dyn.raw": ("%slot", "dyn", ""),
}

SOURCE = """
def size(xs: list[int]) -> int:
    return len(xs)

def as_float(v: int | float) -> float:
    if isinstance(v, int):
        return float(v)
    return v

print(size([1, 2, 3]), as_float(2), as_float(1.5))
"""


def read(op, value="%a0", first=1, line=0):
    t, receiver, member = READS[op]
    i = Ins(op, t, member)
    i.line = line
    i.a = [Val(value, receiver)]
    i.r = [first] if WORD_READS[op] == 0 else [first, first + 1]
    return i


def legacy(i):
    if i.op == "list.len" or i.op == "union.tag":
        return [f"  %t{i.r[0]} = load i64, ptr {i.a[0].v}"]
    if i.op == "dyn.type":
        return [f"  %t{i.r[0]} = load ptr, ptr {i.a[0].v}"]
    return [f"  %t{i.r[0]} = getelementptr i64, ptr {i.a[0].v}, i64 1",
            f"  %t{i.r[1]} = load i64, ptr %t{i.r[0]}"]


def function(blocks):
    fn = IFn(FnInfo("machine", "@machine", Node("def", "machine", 1), ""))
    fn.blocks = []
    for label, code in blocks:
        b = Blk(label)
        b.code = code
        fn.blocks.append(b)
    fn.n = max([n for b in fn.blocks for i in b.code for n in i.r] + [0])
    return fn


def branch(label):
    i = Ins("br", "", "")
    i.b = [label]
    return i


class MachineOpsTests(unittest.TestCase):
    def test_table_names_registered_ops_with_their_result_numbers(self):
        self.assertEqual(sorted(WORD_READS), sorted(READS))
        for op, word in WORD_READS.items():
            with self.subTest(op=op):
                self.assertIn(op, IROPS)
                self.assertEqual(RESULT_NUMBERS[op], 1 if word == 0 else 2)

    def test_each_read_prints_the_text_its_own_lowering_did(self):
        for op in READS:
            for value, first in (("%a0", 1), ("%t41", 42), ("@g.items", 7)):
                with self.subTest(op=op, value=value):
                    i = read(op, value, first)
                    g = Gen()
                    fn = function([("entry", [])])
                    for machine in machine_ops(i):
                        g.lower_ins(fn, machine)
                    self.assertEqual(g.out, legacy(i))

    def test_first_word_is_one_typed_load(self):
        for op in ("list.len", "union.tag", "dyn.type"):
            with self.subTest(op=op):
                i = read(op, "%t3", 9, line=77)
                load, = machine_ops(i)
                self.assertEqual((load.op, load.t, load.s, load.x, load.k, load.b), ("mach.load", READS[op][0], "", "", 0, []))
                self.assertEqual([(a.v, a.t) for a in load.a], [("%t3", "%ptr")])
                self.assertEqual((load.r, load.line), ([9], 77))

    def test_later_word_is_an_address_and_a_slot_load(self):
        for op in ("union.payload", "union.raw", "dyn.payload", "dyn.raw"):
            with self.subTest(op=op):
                i = read(op, "%t3", 9, line=77)
                addr, load = machine_ops(i)
                self.assertEqual((addr.op, addr.t, addr.s, addr.x, addr.k, addr.b), ("mach.addr", "%ptr", "int", "", 0, []))
                self.assertEqual([(a.v, a.t) for a in addr.a], [("%t3", "%ptr"), ("1", "int")])
                self.assertEqual((load.op, load.t, load.s), ("mach.load", "%slot", ""))
                self.assertEqual([(a.v, a.t) for a in load.a], [("%t9", "%ptr")])
                self.assertEqual((addr.r, load.r, addr.line, load.line), ([9], [10], 77, 77))

    def test_the_read_itself_is_left_as_it_was(self):
        i = read("union.payload", "%a0", 5, line=3)
        machine_ops(i)
        self.assertEqual((i.op, i.t, i.s, i.r, i.line), ("union.payload", "%slot", "int", [5, 6], 3))
        self.assertEqual([(a.v, a.t) for a in i.a], [("%a0", "union[int,float]")])


class MachineStageTests(unittest.TestCase):
    def test_stage_rewrites_only_blocks_that_hold_a_read(self):
        ret = Ins("ret.none", "", "")
        phi = Ins("phi", "int", "")
        phi.a = [Val("0", "int")]
        phi.b = ["entry"]
        phi.r = [1]
        length = read("list.len", "%a0", 2)
        payload = read("dyn.payload", "%a1", 3)
        entry = [branch("reads")]
        reads = [phi, length, payload, branch("plain")]
        plain = [ret]
        fn = function([("entry", entry), ("reads", reads), ("plain", plain)])
        n = fn.n
        Gen().machine_ir(fn)
        self.assertIs(fn.blocks[0].code, entry)
        self.assertIs(fn.blocks[2].code, plain)
        self.assertIsNot(fn.blocks[1].code, reads)
        self.assertEqual([i.op for i in fn.blocks[1].code], ["phi", "mach.load", "mach.addr", "mach.load", "br"])
        self.assertIs(fn.blocks[1].code[0], phi)
        self.assertIs(fn.blocks[1].code[-1], reads[-1])
        self.assertEqual([i.r for i in fn.blocks[1].code], [[1], [2], [3], [4], []])
        self.assertEqual(fn.n, n)
        # (the caller's own list of the block's ops still holds the reads)
        self.assertEqual([i.op for i in reads], ["phi", "list.len", "dyn.payload", "br"])

    def test_stage_is_idempotent(self):
        fn = function([("entry", [read("union.tag"), Ins("ret.none", "", "")])])
        g = Gen()
        g.machine_ir(fn)
        code = fn.blocks[0].code
        g.machine_ir(fn)
        self.assertIs(fn.blocks[0].code, code)

    def test_printer_takes_no_layout_read(self):
        for op in READS:
            with self.subTest(op=op):
                errors = StringIO()
                with redirect_stderr(errors), self.assertRaises(SystemExit):
                    Gen().lower_ins(function([("entry", [])]), read(op))
                self.assertIn("no lowering for IR op " + op, errors.getvalue())

    def test_lowering_a_function_runs_the_stage_first(self):
        i = read("dyn.raw", "%a0", 1)
        fn = function([("entry", [i, Ins("ret.none", "", "")])])
        g = Gen()
        g.lower(fn)
        text = "\n".join(g.out).split("\n")
        for line in legacy(i):
            self.assertIn(line, text)
        self.assertEqual([x.op for x in fn.blocks[0].code], ["mach.addr", "mach.load", "ret.none"])


class MachineCheckTests(unittest.TestCase):
    def rejected(self, fn):
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify_machine(fn)
        return errors.getvalue()

    def test_check_accepts_what_the_stage_makes(self):
        fn = function([("entry", [read(op, "%a0", 2 * n + 1) for n, op in enumerate(READS)] + [Ins("ret.none", "", "")])])
        g = Gen()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}):
            g.machine_ir(fn)
        g.verify_machine(fn)

    def test_check_rejects_a_read_the_stage_left(self):
        fn = function([("entry", [read("union.payload"), Ins("ret.none", "", "")])])
        self.assertIn("union.payload left after machine lowering", self.rejected(fn))

    def test_check_rejects_malformed_machine_ops(self):
        for change, message in ((lambda i: setattr(i, "a", [Val("%a0", "dyn")]), "needs a machine pointer address"),
                                (lambda i: setattr(i, "t", "%ovf"), "needs a machine storage value type"),
                                (lambda i: setattr(i, "r", [1, 2]), "with 2 numbers"),
                                (lambda i: setattr(i, "s", "bytes"), "invalid value or memory metadata")):
            with self.subTest(message=message):
                load, = machine_ops(read("list.len"))
                change(load)
                self.assertIn(message, self.rejected(function([("entry", [load, Ins("ret.none", "", "")])])))

    def test_slot_load_is_machine_ir_only(self):
        _, load = machine_ops(read("dyn.payload"))
        fn = function([("entry", [load, Ins("ret.none", "", "")])])
        Gen().verify_machine(fn)
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            Gen().verify(fn, False)
        self.assertIn("mach.load needs a machine storage value type", errors.getvalue())


class CompiledProgramTests(unittest.TestCase):
    def test_compiled_reads_are_lowered_checked_and_printed_as_before(self):
        before = {}
        after = {}
        stage = Gen.machine_ir

        def capture(g, fn):
            before[fn.f.name] = [i for b in fn.blocks for i in b.code]
            stage(g, fn)
            after[fn.f.name] = [i for b in fn.blocks for i in b.code]

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), patch.object(Gen, "machine_ir", capture):
            ir = Gen().program(Loader([]).program("machine.py", SOURCE))
        text = ir.split("\n")
        reads = [i for name in before for i in before[name] if i.op in WORD_READS]
        self.assertIn("list.len", [i.op for i in before["size"]])
        self.assertIn("union.tag", [i.op for i in before["as_float"]])
        self.assertTrue(any(WORD_READS[i.op] == 1 for i in before["as_float"] if i.op in WORD_READS))
        for name in after:
            self.assertEqual([i.op for i in after[name] if i.op in WORD_READS], [])
            # every other op is the same object, in the same order
            self.assertEqual([id(i) for i in after[name] if not i.op.startswith("mach.")],
                             [id(i) for i in before[name] if i.op not in WORD_READS and not i.op.startswith("mach.")])
        for i in reads:
            for line in legacy(i):
                self.assertIn(line, text)


if __name__ == "__main__":
    unittest.main()
