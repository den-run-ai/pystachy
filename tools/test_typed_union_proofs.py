"""Guard, mutation and raw-copy controls for closed-union IR proofs.

Malformed IR is checked only; it is never lowered or executed.
"""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, ClassInfo, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.specs import IROPS
from src.pystachy_compiler.union_state import UnionState

U = "union[int,float]"
W = "union[int,float,str]"


class Case:
    def __init__(self, name, ptypes=None):
        self.g = Gen()
        for t in ("int", "float", "str"):
            self.g.utag(t)
        f = FnInfo(name, "@" + name, Node("def", name, 1), "")
        f.ptypes = ptypes or [U, U, "*" + U, "%ptr"]
        f.params = ["p" + str(i) for i in range(len(f.ptypes))]
        self.fn = IFn(f)
        self.fn.ps = list(range(len(f.ptypes)))
        self.b = self.fn.blocks[0]

    def block(self, label):
        self.b = Blk(label)
        self.fn.blocks.append(self.b)

    def op(self, op, t="", s="", a=(), b=()):
        i = Ins(op, t, s)
        i.a = [Val(*v) for v in a]
        i.b = list(b)
        n = self.g.nums(i)
        i.r = list(range(self.fn.n + 1, self.fn.n + n + 1))
        self.fn.n += n
        self.b.code.append(i)
        return "%t" + str(i.r[-1]) if i.r else ""

    def guard(self, value="%a0", member="int", pred="==", yes="hit", no="miss", typ=U, machine=False):
        tag = self.op("mach.load" if machine else "union.tag", "int", a=[(value, "%ptr" if machine else typ)])
        cmp = self.op("num.cmp", "bool", pred, [(tag, "int"), (str(self.g.utags[member]), "int")])
        self.op("cbr", a=[(cmp, "bool")], b=[yes, no])

    def payload(self, value="%a0", member="int", typ=U, unpack=None):
        bits = self.op("union.payload", "%slot", member, [(value, typ)])
        self.op("slot.unpack", unpack or member, a=[(bits, "%slot")])

    def ret(self):
        self.op("ret.none")

    def finish_pair(self):
        self.ret()
        self.block("miss")
        self.ret()


def basic(name, mode):
    c = Case(name)
    if mode == "none":
        c.payload()
        c.ret()
        return c
    c.guard(machine=mode == "machine")
    c.block("hit")
    c.payload(value="%a1" if mode == "other" else "%a0",
              member="float" if mode == "wrong" else "int",
              unpack="float" if mode == "unpack" else None)
    c.finish_pair()
    return c


def narrowed_spoof():
    c = Case("narrowed_operand_spoof", [W])
    c.guard(typ=W)
    c.block("hit")
    c.ret()
    c.block("miss")
    # The true static source still permits str, though this operand hides it.
    c.payload(member="float", typ=U)
    c.ret()
    return c


def optional_spoof():
    c = Case("optional_operand_spoof", ["opt[" + U + "]"])
    c.guard()  # Annotation on Val falsely removes nullable source's None.
    c.block("hit")
    c.payload()
    c.finish_pair()
    return c


def pointer_spoof():
    c = Case("narrowed_pointer_operand_spoof", ["*" + W])
    v = c.op("mem.load", U, a=[("%a0", "*" + U)])
    c.guard(v)
    c.block("hit")
    c.ret()
    c.block("miss")
    c.payload(v, member="float")
    c.ret()
    return c


def unknown_producer():
    c = Case("unknown_producer_operand_cannot_prove_type")
    c.guard("%unknown")
    c.block("hit")
    c.ret()
    c.block("miss")
    c.payload("%unknown", member="float")
    c.ret()
    return c


def exclusion():
    c = Case("exclusion_last_arm")
    c.guard()
    c.block("hit")
    c.payload()
    c.ret()
    c.block("miss")
    c.payload(member="float")
    c.ret()
    return c


def joined():
    c = Case("joined_guard_no_longer_singleton")
    c.guard()
    for label in ("hit", "miss"):
        c.block(label)
        c.op("br", b=["join"])
    c.block("join")
    c.payload()
    c.ret()
    return c


def same_successor():
    c = Case("both_guard_edges_same_successor")
    c.guard(yes="join", no="join")
    c.block("join")
    c.payload(member="float")
    c.ret()
    return c


def loop_backedge():
    c = Case("loop_backedge_invalidates_first_entry_fact")
    v = c.op("mem.load", U, a=[("%a2", "*" + U)])
    c.guard(v, yes="loop", no="exit")
    c.block("loop")
    v2 = c.op("mem.load", U, a=[("%a2", "*" + U)])
    c.payload(v2)
    c.op("mem.store", a=[("%a2", "*" + U), ("%a1", U)])
    c.op("cbr", a=[("true", "bool")], b=["loop", "exit"])
    c.block("exit")
    c.ret()
    return c


def cold_failure_path():
    c = Case("check_failure_edge_requires_proof", [U, U, "*" + U, "%ptr", "bool"])
    c.fn.cold["ValueError: proof probe"] = "cold"
    c.op("check", s="ValueError: proof probe", a=[("%a4", "bool")], b=["next"])
    c.block("next")
    c.ret()
    c.block("cold")
    c.payload()
    c.ret()
    return c


def mutated(name, old=False, call=False, untouched=False):
    c = Case(name)
    a = "%a2"
    v = c.op("mem.load", U, a=[(a, "*" + U)])
    c.guard(v)
    c.block("hit")
    if call:
        c.op("icall", "None", a=[("%a3", "%ptr"), (a, "*" + U)])
    elif not untouched:
        c.op("mem.store", a=[(a, "*" + U), ("%a1", U)])
    after = v if old else c.op("mem.load", U, a=[(a, "*" + U)])
    c.payload(after)
    c.finish_pair()
    return c


def exceptional(old=False):
    c = Case("exception_old_box" if old else "exception_reload")
    v = c.op("mem.load", U, a=[("%a2", "*" + U)])
    c.guard(v)
    c.block("hit")
    c.op("icall", "None", a=[("%a3", "%ptr"), ("%a2", "*" + U)], b=["normal", "landing"])
    c.block("normal")
    c.ret()
    c.block("landing")
    c.op("landing", "exc", a=[("%a2", "%ptr")], b=["handler"])
    c.block("handler")
    after = v if old else c.op("mem.load", U, a=[("%a2", "*" + U)])
    c.payload(after)
    c.ret()
    c.block("miss")
    c.ret()
    return c


def aliased_store(mode="pointer", old=False):
    name = "alias_" + mode + ("_old_box" if old else "_reload")
    c = Case(name, [U, U, "Box", "Box"] if mode == "field" else [U, U, "*" + U, "*" + U])
    if mode == "field":
        ci = ClassInfo("Box", Node("class", "Box", 1))
        ci.fields = ["value"]
        ci.ftypes = {"value": U}
        c.g.classes["Box"] = ci
        p = c.op("field.addr", "*" + U, a=[("%a2", "Box")])
        q = c.op("field.addr", "*" + U, a=[("%a3", "Box")])
        c.fn.fa[p] = True
        c.fn.fa[q] = True
    else:
        p = "%a2"
        q = "%a3"
        if mode == "gep":
            q = c.op("mach.addr", "%ptr", "%ptr", [(q, "%ptr"), ("0", "int")])
    v = c.op("mem.load", U, a=[(p, "*" + U)])
    c.guard(v)
    c.block("hit")
    # p and q have distinct SSA names but the caller may pass the same address/object.
    c.op("mem.store", a=[(q, "*" + U), ("%a1", U)])
    after = v if old else c.op("mem.load", U, a=[(p, "*" + U)])
    c.payload(after)
    c.finish_pair()
    return c


def raw_parts(c, box):
    tag = c.op("union.tag", "int", a=[(box, U)])
    bits = c.op("union.raw", "%slot", a=[(box, U)])
    return tag, bits


def raw_rebox(mixed=False, phi=False):
    c = Case("raw_" + ("mixed" if mixed else "same") + ("_phi" if phi else "_source"), [U, U, "*" + U, "%ptr", "bool"])
    c.g.runtime("pys_ubox")
    if phi:
        c.op("cbr", a=[("%a4", "bool")], b=["left", "right"])
        c.block("left")
        t0, p0 = raw_parts(c, "%a0")
        _, bad0 = raw_parts(c, "%a1") if mixed else (t0, p0)
        c.op("br", b=["merge"])
        c.block("right")
        t1, p1 = raw_parts(c, "%a1")
        _, bad1 = raw_parts(c, "%a0") if mixed else (t1, p1)
        c.op("br", b=["merge"])
        c.block("merge")
        tag = c.op("phi", "int", a=[(t0, "int"), (t1, "int")], b=["left", "right"])
        bits = c.op("phi", "int", a=[(bad0, "int"), (bad1, "int")], b=["left", "right"])
    else:
        tag, bits = raw_parts(c, "%a0")
        if mixed:
            _, bits = raw_parts(c, "%a1")
    c.op("rt", "%ptr", "ubox", [(tag, "int"), (bits, "*T")])
    c.ret()
    return c


def raw_interpret(direct=False):
    c = Case("raw_direct_int_interpret" if direct else "raw_unguarded_unpack")
    _, bits = raw_parts(c, "%a0")
    if direct:
        c.op("num.cmp", "bool", "==", [(bits, "int"), ("9", "int")])
    else:
        c.op("slot.unpack", "float", a=[(bits, "%slot")])
    c.ret()
    return c


cases = [
    (False, basic("missing_guard", "none")),
    (True, basic("matching_guard", "good")),
    (True, basic("machine_tag_guard", "machine")),
    (False, basic("different_box", "other")),
    (False, basic("wrong_member", "wrong")),
    (False, basic("wrong_unpack_type", "unpack")),
    (False, narrowed_spoof()),
    (False, optional_spoof()),
    (False, pointer_spoof()),
    (False, unknown_producer()),
    (True, exclusion()),
    (False, joined()),
    (False, same_successor()),
    (False, loop_backedge()),
    (False, cold_failure_path()),
    (False, mutated("store_then_reload")),
    (True, mutated("store_preserves_old_box", old=True)),
    (True, mutated("unchanged_reload", untouched=True)),
    (False, mutated("call_then_reload", call=True)),
    (True, mutated("call_preserves_old_box", old=True, call=True)),
    (False, exceptional()),
    (True, exceptional(old=True)),
    (False, aliased_store()),
    (True, aliased_store(old=True)),
    (False, aliased_store("gep")),
    (True, aliased_store("gep", old=True)),
    (False, aliased_store("field")),
    (True, aliased_store("field", old=True)),
]
if "union.raw" in IROPS:
    cases += [(True, raw_rebox()), (False, raw_rebox(mixed=True)),
              (True, raw_rebox(phi=True)), (False, raw_rebox(mixed=True, phi=True)),
              (False, raw_interpret()), (False, raw_interpret(direct=True))]



class UnionProofTests(unittest.TestCase):
    def test_completed_guards_do_not_accumulate_live_proof_facts(self):
        for count in (20, 100):
            with self.subTest(count=count):
                c = Case("sequential_guards", [U])
                for n in range(count):
                    hit, miss, join = "hit" + str(n), "miss" + str(n), "join" + str(n)
                    c.guard(yes=hit, no=miss)
                    c.block(hit)
                    c.payload(member="int")
                    c.op("br", b=[join])
                    c.block(miss)
                    c.payload(member="float")
                    c.op("br", b=[join])
                    c.block(join)
                c.ret()
                sizes = []
                retain = UnionState.retain

                def observe(state, values, retain=retain, sizes=sizes):
                    retain(state, values)
                    sizes.append(len(state.d))

                with patch.object(UnionState, "retain", observe):
                    c.g.verify(c.fn, False)
                self.assertTrue(sizes)
                self.assertLess(max(sizes), 16)

    def test_nullable_condition_survives_an_unrelated_join(self):
        for loop in (False, True):
            for pred in ("!=", "=="):
                with self.subTest(loop=loop, pred=pred):
                    optional = "opt[" + U + "]"
                    c = Case("saved_null_test", [optional, "bool"])
                    condition = c.op("ptr.cmp", "bool", pred, [("%a0", optional), ("null", "None")])
                    if loop:
                        c.op("br", b=["loop"])
                        c.block("loop")
                        c.op("cbr", a=[("%a1", "bool")], b=["loop", "join"])
                    else:
                        c.op("cbr", a=[("%a1", "bool")], b=["left", "right"])
                        for label in ("left", "right"):
                            c.block(label)
                            c.op("br", b=["join"])
                    c.block("join")
                    c.op("cbr", a=[(condition, "bool")], b=["nonnull", "exit"])
                    c.block("nonnull")
                    c.guard(no="exit")
                    c.block("hit")
                    c.payload()
                    c.ret()
                    c.block("exit")
                    c.ret()
                    with redirect_stderr(StringIO()):
                        if pred == "!=":
                            c.g.verify(c.fn, False)
                        else:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)

    def test_only_raising_calls_contribute_handler_edges(self):
        for raises in (False, True):
            with self.subTest(raises=raises):
                c = Case("handler_effects")
                c.b.handler = "handler"
                if raises:
                    c.op("icall", "None", a=[("%a3", "%ptr")])
                else:
                    c.g.runtime("pys_alloc")
                    c.op("rt", "%ptr", "alloc", [("8", "int")])
                c.guard(no="exit")
                c.block("hit")
                c.b.handler = "handler"
                c.op("icall", "None", a=[("%a3", "%ptr")])
                c.ret()
                c.block("handler")
                c.payload()
                c.ret()
                c.block("exit")
                c.ret()
                with redirect_stderr(StringIO()):
                    if raises:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)
                    else:
                        c.g.verify(c.fn, False)

    def test_fresh_float_phi_keeps_its_native_payload_type(self):
        for tag in ("float", "int"):
            with self.subTest(tag=tag):
                c = Case("fresh_float_phi", [U, "float", "float", "bool"])
                c.g.runtime("pys_ubox")
                c.op("union.raw", "%slot", a=[("%a0", U)])
                c.op("cbr", a=[("%a3", "bool")], b=["left", "right"])
                c.block("left")
                c.op("br", b=["join"])
                c.block("right")
                c.op("br", b=["join"])
                c.block("join")
                value = c.op("phi", "float", a=[("%a1", "float"), ("%a2", "float")], b=["left", "right"])
                bits = c.op("slot.pack", "%slot", a=[(value, "float")])
                c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), (bits, "*T")])
                c.ret()
                with redirect_stderr(StringIO()):
                    if tag == "float":
                        c.g.verify(c.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)

    def test_short_circuit_phi_keeps_the_taken_boolean_value(self):
        for bypass in ("false", "true"):
            with self.subTest(bypass=bypass):
                c = Case("short_circuit", [U])
                c.guard(yes="hit", no="miss")
                condition = c.fn.blocks[0].code[-1].a[0].v
                c.block("hit")
                c.op("br", b=["join"])
                c.block("miss")
                c.op("br", b=["join"])
                c.block("join")
                value = c.op("phi", "bool", a=[(condition, "bool"), (bypass, "bool")], b=["hit", "miss"])
                c.op("cbr", a=[(value, "bool")], b=["read", "exit"])
                c.block("read")
                c.payload()
                c.ret()
                c.block("exit")
                c.ret()
                with redirect_stderr(StringIO()):
                    if bypass == "false":
                        c.g.verify(c.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)

    def test_tag_domains_have_no_machine_word_limit(self):
        c = basic("many_tags", "good")
        for n in range(100):
            c.g.utag("Member" + str(n))
        c.g.verify(c.fn, False)

    def test_guard_and_raw_copy_controls(self):
        for expected, case in cases:
            with self.subTest(case=case.fn.f.name):
                errors = StringIO()
                with redirect_stderr(errors):
                    if expected:
                        case.g.verify(case.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            case.g.verify(case.fn, False)
                        self.assertRegex(errors.getvalue(), "(union|payload|ubox)")

    def test_dropping_a_narrowing_guard_is_rejected(self):
        case = basic("dropped_guard", "good")
        case.g.verify(case.fn, False)
        branch = case.fn.blocks[0].code[-1]
        branch.op = "br"
        branch.a = []
        branch.b = ["hit"]
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            case.g.verify(case.fn, False)
        self.assertIn("union.payload needs tag int", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
