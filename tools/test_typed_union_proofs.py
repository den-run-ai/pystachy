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
from src.pystachy_compiler import ircheck
from src.pystachy_compiler.ir import Blk, ClassInfo, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.specs import IROPS
from src.pystachy_compiler.union_state import UnionState
from src.pystachy_compiler.union_proof import UnionProof, simple_union_proof

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
    def test_repeated_union_shapes_are_validated_once_but_each_read_is_checked(self):
        for invalid in (False, True):
            with self.subTest(invalid=invalid):
                c = Case("repeated_union_shape", [U])
                for _ in range(20):
                    c.op("union.tag", "int", a=[("%a0", U)])
                if invalid:
                    c.b.code[-1].s = "int"
                c.ret()
                with patch.object(ircheck, "umembers", wraps=ircheck.umembers) as members:
                    with redirect_stderr(StringIO()):
                        if invalid:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)
                        else:
                            c.g.verify(c.fn, False)
                    self.assertEqual(members.call_count, 1)

    def test_fast_proof_keeps_multiple_tag_tests_tied_to_their_source(self):
        for interleaved in (False, True):
            for guarded in (0, 1):
                for extracted in (0, 1):
                    with self.subTest(interleaved=interleaved, guarded=guarded, extracted=extracted):
                        c = Case("multiple_tag_sources", [U, U])
                        tags = []
                        conditions = []
                        for n in range(2):
                            tags.append(c.op("union.tag", "int", a=[("%a" + str(n), U)]))
                            if interleaved:
                                conditions.append(c.op("num.cmp", "bool", "==", [(tags[n], "int"), (str(c.g.utags["int"]), "int")]))
                        if not interleaved:
                            for tag in tags:
                                conditions.append(c.op("num.cmp", "bool", "==", [(tag, "int"), (str(c.g.utags["int"]), "int")]))
                        c.op("cbr", a=[(conditions[guarded], "bool")], b=["hit", "miss"])
                        c.block("hit")
                        c.payload("%a" + str(extracted))
                        c.finish_pair()
                        if guarded != extracted:
                            self.assertFalse(simple_union_proof(c.fn, c.g.utags))
                        with redirect_stderr(StringIO()):
                            if guarded == extracted:
                                c.g.verify(c.fn, False)
                            else:
                                with self.assertRaises(SystemExit):
                                    c.g.verify(c.fn, False)

    def test_cached_graph_preserves_duplicate_edges_and_bypass_paths(self):
        for make_case in (same_successor, joined, cold_failure_path, loop_backedge):
            with self.subTest(case=make_case.__name__):
                c = make_case()
                calls = []

                def observe(fn, tags, at, successors, calls=calls):
                    self.assertIsNotNone(at)
                    self.assertIsNotNone(successors)
                    cached = simple_union_proof(fn, tags, at, successors)
                    self.assertEqual(cached, simple_union_proof(fn, tags))
                    self.assertFalse(cached)
                    calls.append(True)
                    return cached

                with patch("src.pystachy_compiler.ircheck.simple_union_proof", side_effect=observe):
                    with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                        c.g.verify(c.fn, False)
                self.assertEqual(calls, [True])

    def test_integer_literal_payload_survives_an_unrelated_join(self):
        for tag in ("int", "float"):
            with self.subTest(tag=tag):
                c = Case("literal_join", ["bool"])
                c.g.runtime("pys_ubox")
                c.op("cbr", a=[("%a0", "bool")], b=["left", "right"])
                c.block("left")
                c.op("rt", "%ptr", "ubox", [(str(c.g.utags["int"]), "int"), ("-1", "*T")])
                c.op("br", b=["join"])
                c.block("right")
                c.op("br", b=["join"])
                c.block("join")
                c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), ("-1", "*T")])
                c.ret()
                with redirect_stderr(StringIO()):
                    if tag == "int":
                        c.g.verify(c.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)

    def test_specialized_list_load_retains_declared_element_type(self):
        for element in ("int", "float"):
            for tag in ("int", "float"):
                with self.subTest(element=element, tag=tag):
                    c = Case("list_load_type", ["list[" + element + "]"])
                    c.g.runtime("pys_ubox")
                    c.op("list.load", "*T", a=[("%a0", "S"), ("0", "int")])
                    value = "%t" + str(c.b.code[-1].r[0])
                    c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), (value, "*T")])
                    c.ret()
                    with redirect_stderr(StringIO()):
                        if tag == element:
                            c.g.verify(c.fn, False)
                        else:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)

    def test_generic_list_element_instantiation_cannot_retype_concrete_or_raw_bits(self):
        for source in ("generic", "specialized", "float", "raw"):
            for tag in ("int", "float"):
                with self.subTest(source=source, tag=tag):
                    c = Case("generic_storage_type", ["list[float]", U])
                    c.g.runtime("pys_ubox")
                    c.g.runtime("pys_list_new")
                    c.g.runtime("pys_list_get")
                    slot = Ins("slot", "int", "local")
                    c.fn.n += 1
                    slot.r = [c.fn.n]
                    c.fn.slots.append(slot)
                    address = "%local." + str(slot.r[0])
                    if source == "raw":
                        value = c.op("union.raw", "%slot", a=[("%a1", U)])
                    else:
                        receiver = "%a0" if source == "float" else c.op("rt", "list[T]", "list.new", [("1", "int")])
                        if source == "specialized":
                            c.op("list.load", "*T", a=[(receiver, "S"), ("0", "int")])
                            value = "%t" + str(c.b.code[-1].r[0])
                        else:
                            value = c.op("rt", "*T", "list.get", [(receiver, "S"), ("0", "int")])
                    # Only the generic element is instantiated here. A concrete float
                    # or an opaque union payload cannot be relabelled by this annotation.
                    c.op("mem.store", a=[(address, "*int"), (value, "int")])
                    loaded = c.op("mem.load", "int", a=[(address, "*int")])
                    c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), (loaded, "*T")])
                    c.ret()
                    valid = source in ("generic", "specialized") and tag == "int"
                    # The malformed float store still carries float provenance.
                    valid = valid or (source == "float" and tag == "float")
                    with redirect_stderr(StringIO()):
                        if valid:
                            c.g.verify(c.fn, False)
                        else:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)

    def test_homogeneous_tuple_machine_load_retains_element_contract(self):
        for elements in ("int,int", "float,float", "int,float"):
            for tag in ("int", "float"):
                with self.subTest(elements=elements, tag=tag):
                    c = Case("tuple_machine_type", ["int"])
                    c.g.runtime("pys_alloc")
                    c.g.runtime("pys_ubox")
                    owner = c.op("alloc.fixed", "tuple[" + elements + "]")
                    address = c.op("mach.addr", "%ptr", "int", [(owner, "%ptr"), ("%a0", "int")])
                    value = c.op("mach.load", "int", a=[(address, "%ptr")])
                    c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), (value, "*T")])
                    c.ret()
                    with redirect_stderr(StringIO()):
                        if elements == tag + "," + tag:
                            c.g.verify(c.fn, False)
                        else:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)

    def test_fast_proof_requires_an_immutable_private_slot(self):
        for mode in ("immutable", "store", "escape", "alias", "optional", "before_init", "scalar_load"):
            with self.subTest(mode=mode):
                typ = "opt[" + U + "]" if mode == "optional" else U
                c = Case("private_slot_" + mode, [U, U, "%ptr"])
                slot = Ins("slot", typ, "local")
                c.fn.n += 1
                slot.r = [c.fn.n]
                c.fn.slots.append(slot)
                address = "%local." + str(slot.r[0])
                if mode == "before_init":
                    c.op("mem.load", U, a=[(address, "*" + U)])
                c.op("mem.store", a=[(address, "*" + typ), ("null" if mode == "optional" else "%a0", typ)])
                value = c.op("mem.load", "int" if mode == "scalar_load" else U,
                             a=[(address, "*int" if mode == "scalar_load" else "*" + U)])
                c.guard(value)
                c.block("hit")
                if mode == "store":
                    c.op("mem.store", a=[(address, "*" + U), ("%a1", U)])
                elif mode == "escape":
                    c.op("icall", "None", a=[("%a2", "%ptr"), (address, "*" + U)])
                elif mode == "alias":
                    alias = c.op("mach.addr", "%ptr", "%ptr", [(address, "%ptr"), ("0", "int")])
                    c.op("mach.store", a=[(alias, "%ptr"), ("%a1", U)])
                value = c.op("mem.load", U, a=[(address, "*" + U)])
                c.payload(value)
                c.finish_pair()
                self.assertEqual(simple_union_proof(c.fn, c.g.utags), mode == "immutable")
                # Initialization and SSA machine types have their own contracts; the
                # shortcut must defer them without claiming a stronger general check.
                if mode not in ("before_init", "scalar_load"):
                    with redirect_stderr(StringIO()):
                        if mode == "immutable":
                            c.g.verify(c.fn, False)
                        else:
                            with self.assertRaises(SystemExit):
                                c.g.verify(c.fn, False)

    def test_fast_proof_rejects_payload_address_escapes_and_reinterpretation(self):
        for mode in ("address_load", "address_call", "direct", "pack", "select"):
            with self.subTest(mode=mode):
                c = Case("payload_escape_" + mode)
                c.guard()
                c.block("hit")
                bits = c.op("union.payload", "%slot", "int", [("%a0", U)])
                address = "%t" + str(c.b.code[-1].r[0])
                if mode == "address_load":
                    c.op("mach.load", "float", a=[(address, "%ptr")])
                elif mode == "address_call":
                    c.op("icall", "None", a=[("%a3", "%ptr"), (address, "%ptr")])
                else:
                    if mode == "pack":
                        bits = c.op("slot.pack", "%slot", a=[(bits, "float")])
                    elif mode == "select":
                        bits = c.op("select", "%slot", a=[("true", "bool"), (bits, "%slot"), ("0", "%slot")])
                    c.op("slot.unpack", "float", a=[(bits, "%slot")])
                c.finish_pair()
                self.assertFalse(simple_union_proof(c.fn, c.g.utags))
                with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                    c.g.verify(c.fn, False)

    def test_fast_proof_defers_saved_conditions_and_loop_joins(self):
        for loop in (False, True):
            with self.subTest(loop=loop):
                c = Case("saved_condition_loop" if loop else "saved_condition_diamond", [U, "bool"])
                tag = c.op("union.tag", "int", a=[("%a0", U)])
                condition = c.op("num.cmp", "bool", "==", [(tag, "int"), (str(c.g.utags["int"]), "int")])
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
                c.op("cbr", a=[(condition, "bool")], b=["hit", "miss"])
                c.block("hit")
                c.payload()
                c.finish_pair()
                self.assertFalse(simple_union_proof(c.fn, c.g.utags))
                c.g.verify(c.fn, False)

    def test_fast_proof_uses_closed_nonnullable_declarations(self):
        c = Case("nullable_member_hidden_by_operand", ["union[int,float,None]"])
        c.op("union.tag", "int", a=[("%a0", U)])
        c.ret()
        self.assertFalse(simple_union_proof(c.fn, c.g.utags))
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            c.g.verify(c.fn, False)

    def test_fast_proof_does_not_infer_integer_tests_from_float_metadata(self):
        c = basic("tag_comparison_float_metadata", "good")
        comparison = c.fn.blocks[0].code[1]
        for operand in comparison.a:
            operand.t = "float"
        self.assertFalse(simple_union_proof(c.fn, c.g.utags))

    def test_standalone_tag_read_requires_a_nonnull_source(self):
        optional = "opt[" + U + "]"
        for typ, guard in ((U, ""), (optional, ""), (optional, "!="), (optional, "==")):
            with self.subTest(typ=typ, guard=guard):
                c = Case("standalone_tag", [typ])
                if guard:
                    condition = c.op("ptr.cmp", "bool", guard, [("%a0", typ), ("null", "None")])
                    c.op("cbr", a=[(condition, "bool")], b=["read", "exit"])
                    c.block("read")
                # The operand annotation cannot erase None from the parameter's type.
                c.op("union.tag", "int", a=[("%a0", U)])
                c.ret()
                if guard:
                    c.block("exit")
                    c.ret()
                errors = StringIO()
                with redirect_stderr(errors):
                    if typ == U or guard == "!=":
                        c.g.verify(c.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)
                        self.assertIn("union.tag needs a nonnull proof", errors.getvalue())

    def test_standalone_box_requires_matching_tag_and_payload(self):
        for tag in ("float", "int"):
            with self.subTest(tag=tag):
                c = Case("standalone_box", ["float"])
                c.g.runtime("pys_ubox")
                bits = c.op("slot.pack", "%slot", a=[("%a0", "float")])
                c.op("rt", "%ptr", "ubox", [(str(c.g.utags[tag]), "int"), (bits, "*T")])
                c.ret()
                errors = StringIO()
                with redirect_stderr(errors):
                    if tag == "float":
                        c.g.verify(c.fn, False)
                    else:
                        with self.assertRaises(SystemExit):
                            c.g.verify(c.fn, False)
                        self.assertIn("ubox needs matching tag and payload provenance", errors.getvalue())

    def test_machine_tag_read_requires_a_nonnull_source(self):
        optional = "opt[" + U + "]"
        for loaded in (False, True):
            for guard in ("", "!=", "=="):
                for payload in (False, True):
                    with self.subTest(loaded=loaded, guard=guard, payload=payload):
                        # The unrelated nonoptional parameter must not hide this read
                        # from a shortcut that recognizes only immutable union sources.
                        c = Case("nullable_machine_tag", ["*" + optional if loaded else optional, U])
                        value = c.op("mem.load", optional, a=[("%a0", "*" + optional)]) if loaded else "%a0"
                        if guard:
                            condition = c.op("ptr.cmp", "bool", guard, [(value, optional), ("null", "None")])
                            c.op("cbr", a=[(condition, "bool")], b=["read", "exit"])
                            c.block("read")
                        if payload:
                            c.guard(value, machine=True, no="exit")
                            c.block("hit")
                            c.payload(value)
                        else:
                            c.op("mach.load", "int", a=[(value, "%ptr")])
                        c.ret()
                        if guard or payload:
                            c.block("exit")
                            c.ret()
                        errors = StringIO()
                        with redirect_stderr(errors):
                            if guard == "!=":
                                c.g.verify(c.fn, False)
                            else:
                                with self.assertRaises(SystemExit):
                                    c.g.verify(c.fn, False)
                                self.assertIn("mach.load needs a nonnull proof", errors.getvalue())

    def test_unrelated_machine_integer_read_does_not_start_union_proof(self):
        c = Case("unrelated_machine_read", [U, "%ptr"])
        c.op("mach.load", "int", a=[("%a1", "%ptr")])
        c.ret()
        with patch("src.pystachy_compiler.ircheck.UnionProof", side_effect=AssertionError("unrelated memory read")):
            c.g.verify(c.fn, False)

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
                    proof = UnionProof(c.fn, c.g.utags)
                    proof.run()
                    self.assertEqual(proof.bad, [])
                self.assertTrue(simple_union_proof(c.fn, c.g.utags))
                with patch.object(UnionProof, "__init__", side_effect=AssertionError("general solver")):
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
                        self.assertFalse(simple_union_proof(case.fn, case.g.utags))
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
