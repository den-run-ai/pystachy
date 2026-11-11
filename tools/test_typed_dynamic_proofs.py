"""Dynamic-tag guard regressions over typed IR, without lowering unsafe IR."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pystachy_compiler.dynamic_proof import DK_OBJ, DF_ROLE, DynamicProof, DynTypes
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, Data, FnInfo, IFn, Ins, Val, slot_register
from src.pystachy_compiler.syntax import Node


class Case:
    def __init__(self, name="dynamic_guard", ptypes=None):
        self.g = Gen()
        f = FnInfo(name, "@" + name, Node("def", name, 1), "")
        f.ptypes = ptypes or ["dyn", "dyn", "bool", "*dyn", "%ptr"]
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

    def slot(self, typ="dyn", name="local"):
        i = Ins("slot", typ, name)
        self.fn.n += 1
        i.r = [self.fn.n]
        self.fn.slots.append(i)
        return "%" + name + "." + str(i.r[0])

    def shared_slot(self, local, typ, name, kind=0):
        # a slot under local's number, as a local's "is assigned" flag (kind 1) and its numeric
        # identity companions are declared (emission.py)
        i = Ins("slot", typ, name)
        i.k = kind
        i.r = [int(local.rsplit(".", 1)[1])]
        self.fn.slots.append(i)
        return slot_register(i)

    def load(self, address, typ="dyn"):
        return self.op("mem.load", typ, a=[(address, "*" + typ)])

    def store(self, address, value, typ="dyn"):
        self.op("mem.store", a=[(address, "*" + typ), (value, typ)])

    def compare(self, value="%a0", member="float", pred="==", swap=False):
        tag = self.op("dyn.type", "dyntype", a=[(value, "dyn")])
        operands = [(tag, "dyntype"), ("@pys_dyntype_" + member, "dyntype")]
        return self.op("ptr.cmp", "bool", pred, list(reversed(operands)) if swap else operands)

    def branch(self, condition, yes="hit", no="miss"):
        self.op("cbr", a=[(condition, "bool")], b=[yes, no])

    def guard(self, value="%a0", member="float", pred="==", swap=False):
        condition = self.compare(value, member, pred, swap)
        self.branch(condition, "hit" if pred == "==" else "miss", "miss" if pred == "==" else "hit")

    def payload(self, value="%a0", member="float"):
        return self.op("dyn.payload", "%slot", member, [(value, "dyn")])

    def ret(self):
        self.op("ret.none")

    def finish_pair(self):
        self.ret()
        self.block("miss")
        self.ret()

    def dyntype(self, name, kind=DK_OBJ, number=-1, base="", role="", held=""):
        # one of the program's DynTypes, as dynamic.py's dyn_class_type emits a class's: held
        # names the static type of its boxes' payload (the class)
        d = Data("dyntype", name)
        flags = DF_ROLE if role else 0
        d.items = [Val(str(kind), "int"), Val(str(number), "int"), Val(str(flags), "int")]
        d.refs = ["@s.desc", "@s.name", base or "null", "null", "null", "null"] + ([role] if role else [])
        self.g.consts.append(d)
        if held:
            self.g.dyntypes[held] = name
        return name

    def isa_call(self, value="%a0", descriptor="@dt.Base", role=False):
        # pys_dyn_isa (or pys_dyn_role_isa) of value and a DynType: its integer result
        key = self.g.runtime("pys_dyn_role_isa" if role else "pys_dyn_isa")
        return self.op("rt", "bool", key, [(value, "%ptr"), (descriptor, "%ptr")])

    def isa(self, value="%a0", descriptor="@dt.Base", role=False, none=False):
        # dyn_test's test of a class: pys_dyn_isa (or pys_dyn_role_isa), and, unless none,
        # not None, which pys_dyn_isa admits as a class's optional object
        isa = self.isa_call(value, descriptor, role)
        hit = self.op("num.cmp", "bool", "!=", [(isa, "int"), ("0", "int")])
        if none:
            return hit
        notnone = self.compare(value, "none", "!=")
        return self.op("scalar.bin", "bool", "and", [(hit, "bool"), (notnone, "bool")])

    def dispatch(self, cases, value="%a0", word="3", operand=None):
        # a class dispatcher's switch on the class number word of value's DynType: cases maps
        # each class number to its block; the rest go to "miss"
        tag = self.op("dyn.type", "dyntype", a=[(value, "dyn")])
        address = self.op("mach.addr", "%ptr", "int", [(tag, "%ptr"), (word, "int")])
        number = self.op("mach.load", "int", a=[(address, "%ptr")])
        self.op("switch", a=[(operand or number, "int")] + [(n, "int") for n in cases],
                b=["miss"] + list(cases.values()))

    def proof(self):
        proof = DynamicProof(self.fn, DynTypes(self.g.consts, self.g.dyntypes, self.g.dynfnt))
        proof.run()
        return proof


class DynamicGuardTests(unittest.TestCase):
    def assert_safe(self, case, safe=True):
        self.assertEqual(not case.proof().bad, safe, case.proof().bad)

    def test_exact_builtin_tags_and_operand_orders(self):
        for member in ("float", "str", "bool"):
            for pred in ("==", "!="):
                for swap in (False, True):
                    with self.subTest(member=member, pred=pred, swap=swap):
                        c = Case()
                        c.guard(member=member, pred=pred, swap=swap)
                        c.block("hit")
                        c.payload(member=member)
                        c.finish_pair()
                        self.assert_safe(c)
                        c.g.verify(c.fn, False)

    def test_missing_wrong_value_wrong_tag_and_wrong_branch(self):
        for mode in ("missing", "value", "tag", "branch", "same_successor"):
            with self.subTest(mode=mode):
                c = Case()
                if mode == "missing":
                    c.payload()
                    c.ret()
                else:
                    condition = c.compare()
                    c.branch(condition, "miss" if mode == "branch" else "hit",
                             "hit" if mode in ("branch", "same_successor") else "miss")
                    c.block("hit")
                    c.payload("%a1" if mode == "value" else "%a0", "str" if mode == "tag" else "float")
                    c.finish_pair()
                self.assert_safe(c, False)

    def test_excluding_known_tags_keeps_the_unknown_case(self):
        c = Case()
        other_bool = c.compare(member="bool", pred="!=")
        other_str = c.compare(member="str", pred="!=")
        condition = c.op("scalar.bin", "bool", "and", [(other_bool, "bool"), (other_str, "bool")])
        c.branch(condition)
        c.block("hit")
        c.payload()
        c.finish_pair()
        self.assert_safe(c, False)

    def test_boolean_singletons_have_exact_bool_tags(self):
        for value in ("@pys_dyn_true_box", "@pys_dyn_false_box"):
            for member in ("bool", "float"):
                c = Case()
                c.payload(value, member)
                c.ret()
                self.assert_safe(c, member == "bool")

    def test_boolean_combinations_and_negation(self):
        for op, rhs, invert, safe in (("and", "%a2", False, True), ("or", "%a2", False, False),
                                      ("or", "false", False, True), ("xor", "true", True, True)):
            with self.subTest(op=op, rhs=rhs):
                c = Case()
                condition = c.compare()
                condition = c.op("scalar.bin", "bool", op, [(condition, "bool"), (rhs, "bool")])
                c.branch(condition, "miss" if invert else "hit", "hit" if invert else "miss")
                c.block("hit")
                c.payload()
                c.finish_pair()
                self.assert_safe(c, safe)

    def test_private_rebinding_preserves_only_the_old_ssa_value(self):
        for old in (False, True):
            c = Case()
            slot = c.slot()
            c.store(slot, "%a0")
            value = c.load(slot)
            c.guard(value)
            c.block("hit")
            c.store(slot, "%a1")
            c.payload(value if old else c.load(slot))
            c.finish_pair()
            self.assert_safe(c, old)

    def test_slots_sharing_a_local_number_keep_their_own_names_and_types(self):
        # A flag or companion named by number alone would retype the local's own slot.
        for guarded in (True, False):
            with self.subTest(guarded=guarded):
                c = Case()
                slot = c.slot()
                number = slot.rsplit(".", 1)[1]
                flag = c.shared_slot(slot, "bool", "local", 1)
                box = c.shared_slot(slot, "dyn", "local.box")
                generation = c.shared_slot(slot, "int", "local.boxgen")
                self.assertEqual([flag, box, generation],
                                 ["%local.def." + number, "%local.box." + number, "%local.boxgen." + number])
                c.store(slot, "%a0")
                c.store(flag, "true", "bool")
                c.store(box, "%a1")
                c.store(generation, "1", "int")
                if guarded:
                    c.guard(c.load(slot))
                    c.block("hit")
                c.payload(c.load(slot))
                if guarded:
                    c.finish_pair()
                else:
                    c.ret()
                self.assert_safe(c, guarded)
                if guarded:
                    c.g.verify(c.fn, False)

    def test_a_guarded_local_does_not_prove_its_companion_box(self):
        c = Case()
        slot = c.slot()
        box = c.shared_slot(slot, "dyn", "local.box")
        c.store(slot, "%a0")
        c.store(box, "%a1")
        c.guard(c.load(slot))
        c.block("hit")
        c.payload(c.load(box))
        c.finish_pair()
        self.assert_safe(c, False)

    def test_calls_preserve_private_storage_but_escaped_reloads_lose_facts(self):
        for escaped, old in ((False, False), (True, False), (True, True)):
            c = Case()
            slot = c.slot()
            c.store(slot, "%a0")
            value = c.load(slot)
            c.guard(value)
            c.block("hit")
            args = [("%a4", "%ptr")] + ([(slot, "*dyn")] if escaped else [])
            c.op("icall", "None", a=args)
            c.payload(value if old else c.load(slot))
            c.finish_pair()
            self.assert_safe(c, old or not escaped)

    def test_any_address_escape_disables_private_memory_facts(self):
        for mode in ("alias", "store"):
            c = Case()
            slot = c.slot()
            c.store(slot, "%a0")
            value = c.load(slot)
            c.guard(value)
            c.block("hit")
            # The whole-function escape check also sees uses after a guarded reload.
            c.payload(c.load(slot))
            if mode == "alias":
                c.op("mach.addr", "%ptr", "%ptr", [(slot, "%ptr"), ("0", "int")])
            else:
                c.op("mem.store", a=[("@escaped", "**dyn"), (slot, "*dyn")])
            c.finish_pair()
            self.assert_safe(c, False)

    def test_global_field_and_external_slot_reloads_cannot_borrow_guards(self):
        for address in ("@global", "%field", "%a3"):
            for old in (False, True):
                c = Case()
                value = c.load(address)
                c.guard(value)
                c.block("hit")
                c.op("icall", "None", a=[("%a4", "%ptr")])
                c.payload(value if old else c.load(address))
                c.finish_pair()
                self.assert_safe(c, old)

    def test_private_tag_and_boolean_copies(self):
        c = Case()
        tag = c.op("dyn.type", "dyntype", a=[("%a0", "dyn")])
        tag_slot, bool_slot = c.slot("dyntype", "tag"), c.slot("bool", "flag")
        c.store(tag_slot, tag, "dyntype")
        tag = c.load(tag_slot, "dyntype")
        condition = c.op("ptr.cmp", "bool", "==", [(tag, "dyntype"), ("@pys_dyntype_float", "dyntype")])
        c.store(bool_slot, condition, "bool")
        c.branch(c.load(bool_slot, "bool"))
        c.block("hit")
        c.payload()
        c.finish_pair()
        self.assert_safe(c)

    def test_select_requires_every_possible_value_to_match(self):
        for other in ("%a0", "%a1"):
            c = Case()
            condition = c.compare()
            selected = c.op("select", "bool", a=[(condition, "bool"), ("true", "bool"), ("false", "bool")])
            c.branch(selected)
            c.block("hit")
            value = c.op("select", "dyn", a=[("%a2", "bool"), ("%a0", "dyn"), (other, "dyn")])
            c.payload(value)
            c.finish_pair()
            self.assert_safe(c, other == "%a0")

    def test_join_needs_all_incoming_guards(self):
        for guarded in (False, True):
            c = Case()
            c.branch("%a2", "left", "right")
            for label, value in (("left", "%a0"), ("right", "%a1")):
                c.block(label)
                if label == "left" or guarded:
                    c.branch(c.compare(value), label + "_hit", "miss")
                    c.block(label + "_hit")
                c.op("br", b=["join"])
            c.block("join")
            value = c.op("phi", "dyn", a=[("%a0", "dyn"), ("%a1", "dyn")],
                         b=["left_hit", "right_hit" if guarded else "right"])
            c.payload(value)
            c.finish_pair()
            self.assert_safe(c, guarded)

    def test_later_backedge_invalidates_first_iteration_proof(self):
        c = Case()
        slot = c.slot()
        c.store(slot, "%a0")
        c.branch(c.compare(c.load(slot)), "loop", "miss")
        c.block("loop")
        c.payload(c.load(slot))
        c.store(slot, "%a1")
        c.branch("%a2", "loop", "miss")
        c.block("miss")
        c.ret()
        self.assert_safe(c, False)

    def test_exception_handler_uses_state_at_throwing_operation(self):
        for guarded in (False, True):
            c = Case()
            if guarded:
                c.guard()
                c.block("hit")
            c.b.handler = "handler"
            c.op("icall", "None", a=[("%a4", "%ptr")])
            if not guarded:
                c.guard()
                c.block("hit")
            c.finish_pair()
            c.block("handler")
            c.payload()
            c.ret()
            self.assert_safe(c, guarded)

    def test_explicit_invoke_successors_preserve_guarded_ssa(self):
        for guarded in (False, True):
            c = Case()
            if guarded:
                c.guard()
                c.block("hit")
            c.op("icall", "None", a=[("%a4", "%ptr")], b=["normal", "landing"])
            c.block("normal")
            c.ret()
            c.block("landing")
            c.payload()
            c.ret()
            if guarded:
                c.block("miss")
                c.ret()
            self.assert_safe(c, guarded)

    def test_check_normal_and_cold_edges_have_opposite_conditions(self):
        for on_cold in (False, True):
            c = Case()
            condition = c.compare(pred="!=")
            c.fn.cold["TypeError: wrong tag"] = "cold"
            c.op("check", s="TypeError: wrong tag", a=[(condition, "bool")], b=["normal"])
            for label in ("normal", "cold"):
                c.block(label)
                if (label == "cold") == on_cold:
                    c.payload()
                c.ret()
            self.assert_safe(c, not on_cold)

    def test_forged_private_slot_annotations_cannot_supply_facts(self):
        for mode in ("load", "store"):
            c = Case()
            slot = c.slot()
            if mode == "store":
                c.op("mem.store", a=[(slot, "*dyntype"), ("@pys_dyntype_float", "dyntype")])
                value = c.load(slot)
            else:
                c.store(slot, "%a0")
                value = c.load(slot, "dyntype")
            c.payload(value)
            c.ret()
            self.assertTrue(any("matching private " + mode + " types" in x for x in c.proof().bad))

    def test_unreachable_payload_is_not_a_reachable_obligation(self):
        c = Case()
        c.branch("true", "done", "dead")
        c.block("done")
        c.ret()
        c.block("dead")
        c.payload()
        c.ret()
        self.assert_safe(c)

    def test_int_reads_accept_int_or_bool_tags(self):
        # A bool's payload is its int value, so an int read accepts either box.
        for members, safe in ((["int"], True), (["bool"], True), (["int", "bool"], True),
                              (["float"], False), (["bigint"], False), (["int", "float"], False)):
            with self.subTest(members=members):
                c = Case()
                tests = [c.compare(member=member) for member in members]
                condition = tests[0] if len(tests) == 1 else c.op(
                    "scalar.bin", "bool", "or", [(tests[0], "bool"), (tests[1], "bool")])
                c.branch(condition)
                c.block("hit")
                c.payload(member="int")
                c.finish_pair()
                self.assert_safe(c, safe)
                if safe:
                    c.g.verify(c.fn, False)

    def test_int_read_needs_none_excluded_after_its_check(self):
        # A slice bound's check admits None, an int or a bool: its int payload may be read
        # only where a further test excluded None (None's box holds no int).
        for exclude_none in (False, True):
            with self.subTest(exclude_none=exclude_none):
                c = Case()
                none = c.compare(member="none")
                integer = c.op("scalar.bin", "bool", "or", [(c.compare(member="int"), "bool"),
                                                            (c.compare(member="bool"), "bool")])
                ok = c.op("scalar.bin", "bool", "or", [(none, "bool"), (integer, "bool")])
                bad = c.op("scalar.bin", "bool", "xor", [(ok, "bool"), ("true", "bool")])
                c.op("check", s="TypeError", a=[(bad, "bool")], b=["checked"])
                c.fn.cold["TypeError"] = "miss"
                c.block("checked")
                if exclude_none:
                    c.branch(none, "miss", "hit")
                    c.block("hit")
                c.payload(member="int")
                c.finish_pair()
                self.assert_safe(c, exclude_none)

    def test_none_box_is_not_an_int(self):
        c = Case()
        c.payload("@pys_dyn_none_box", "int")
        c.ret()
        self.assert_safe(c, False)


    def test_stock_verifier_rejects_a_missing_dynamic_guard(self):
        c = Case()
        c.payload()
        c.ret()
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            c.g.verify(c.fn, False)
        self.assertIn("dyn.payload of float needs tag @pys_dyntype_float for %a0", errors.getvalue())



class ClassAndContainerGuardTests(unittest.TestCase):
    """Payload reads of classes, containers and functions against the program's DynTypes."""

    def assert_safe(self, case, safe=True):
        bad = case.proof().bad
        self.assertEqual(not bad, safe, bad)

    @staticmethod
    def classes():
        # Base (class number 0), its subclass Child (1) and an unrelated Other (2)
        c = Case()
        base = c.dyntype("@dt.Base", number=0, held="Base")
        c.dyntype("@dt.Child", number=1, base=base, held="Child")
        c.dyntype("@dt.Other", number=2, held="Other")
        return c

    def exact(self, c, descriptor, value="%a0", pred="=="):
        tag = c.op("dyn.type", "dyntype", a=[(value, "dyn")])
        return c.op("ptr.cmp", "bool", pred, [(tag, "dyntype"), (descriptor, "dyntype")])

    def test_isa_admits_none_until_a_test_excludes_it(self):
        # pys_dyn_isa takes None as a class's optional object: dyn_test excludes it.
        for none in (False, True):
            with self.subTest(none=none):
                c = self.classes()
                c.branch(c.isa(none=none))
                c.block("hit")
                c.payload(member="Base")
                c.finish_pair()
                self.assert_safe(c, not none)
                if not none:
                    c.g.verify(c.fn, False)

    def test_isa_proves_its_class_and_bases_but_not_subclasses(self):
        for descriptor, member, safe in (("@dt.Base", "Base", True), ("@dt.Child", "Base", True),
                                         ("@dt.Child", "Child", True), ("@dt.Base", "Child", False),
                                         ("@dt.Base", "Other", False)):
            with self.subTest(descriptor=descriptor, member=member):
                c = self.classes()
                c.branch(c.isa(descriptor=descriptor))
                c.block("hit")
                c.payload(member=member)
                c.finish_pair()
                self.assert_safe(c, safe)

    def test_a_zero_isa_result_proves_the_other_branch(self):
        for exclude_none in (False, True):
            with self.subTest(exclude_none=exclude_none):
                c = self.classes()
                isa = c.isa_call()
                c.branch(c.op("num.cmp", "bool", "==", [(isa, "int"), ("0", "int")]), "miss", "passed")
                c.block("passed")
                if exclude_none:
                    c.branch(c.compare(member="none", pred="!="))
                else:
                    c.op("br", b=["hit"])
                c.block("hit")
                c.payload(member="Base")
                c.finish_pair()
                self.assert_safe(c, exclude_none)

    def test_exact_class_and_container_tags(self):
        for descriptor, member, safe in (
                ("@dt.Child", "Base", True), ("@dt.Child", "Child", True), ("@dt.Base", "Child", False),
                ("@dt.Other", "Base", False), ("@pys_dyntype_list", "list[dyn]", True),
                ("@pys_dyntype_dict", "dict[dyn,dyn]", True), ("@pys_dyntype_tuple", "vtuple[dyn]", True),
                ("@pys_dyntype_intlist", "list[int]", True), ("@pys_dyntype_biglist", "list[int]", True),
                ("@pys_dyntype_list", "list[int]", False), ("@pys_dyntype_tuple", "list[dyn]", False),
                ("@pys_dyntype_dict", "Base", False), ("@dt.Base", "dict[dyn,dyn]", False)):
            with self.subTest(descriptor=descriptor, member=member):
                c = self.classes()
                c.branch(self.exact(c, descriptor))
                c.block("hit")
                c.payload(member=member)
                c.finish_pair()
                self.assert_safe(c, safe)

    def test_excluding_one_class_keeps_every_other_dyntype(self):
        c = self.classes()
        c.branch(self.exact(c, "@dt.Child", pred="!="))
        c.block("hit")
        c.payload(member="Base")
        c.finish_pair()
        self.assert_safe(c, False)

    def test_class_dispatch_arms_and_default(self):
        # each arm reads its own class (a subclass's arm may read its base's payload)
        for arms, default, safe in ((("Base", "Child"), "", True), (("Base", "Base"), "", True),
                                    (("Child", "Child"), "", False), (("Base", "Other"), "", False),
                                    (("Base", "Child"), "Base", False)):
            with self.subTest(arms=arms, default=default):
                c = self.classes()
                c.dispatch({"0": "base", "1": "child"})
                for label, member in zip(("base", "child"), arms):
                    c.block(label)
                    c.payload(member=member)
                    c.ret()
                c.block("miss")
                if default:
                    c.payload(member=default)
                c.ret()
                self.assert_safe(c, safe)
                if safe:
                    c.g.verify(c.fn, False)

    def test_a_switch_proves_only_its_own_tags_class_number(self):
        for mode in ("other box", "other word", "parameter", "unknown number"):
            with self.subTest(mode=mode):
                c = self.classes()
                if mode == "unknown number":
                    c.dispatch({"7": "base"})
                else:
                    c.dispatch({"0": "base"}, value="%a1" if mode == "other box" else "%a0",
                               word="2" if mode == "other word" else "3",
                               operand="%a4" if mode == "parameter" else None)
                c.block("base")
                c.payload(member="Base")
                c.finish_pair()
                self.assert_safe(c, False)

    def test_a_dispatch_listed_before_its_tags_block(self):
        # Block order is not dominance order: list the switch's block before the block that
        # reads the tag it dispatches on, which runs first.
        c = self.classes()
        c.op("br", b=["tag"])
        c.block("tag")
        tag = c.op("dyn.type", "dyntype", a=[("%a0", "dyn")])
        c.op("br", b=["dispatch"])
        c.block("dispatch")
        address = c.op("mach.addr", "%ptr", "int", [(tag, "%ptr"), ("3", "int")])
        number = c.op("mach.load", "int", a=[(address, "%ptr")])
        c.op("switch", a=[(number, "int"), ("0", "int")], b=["miss", "base"])
        c.block("base")
        c.payload(member="Base")
        c.finish_pair()
        blocks = c.fn.blocks
        c.fn.blocks = [blocks[0], blocks[2], blocks[1]] + blocks[3:]
        self.assert_safe(c)

    def test_role_tests_admit_the_classes_that_take_the_role(self):
        for role_test, member, safe in ((True, "Role", True), (False, "Role", True),
                                        (True, "Impl", False)):
            with self.subTest(role_test=role_test, member=member):
                c = Case()
                role = c.dyntype("@dt.Role", number=0, held="Role")
                c.dyntype("@dt.Impl", number=1, role=role, held="Impl")
                c.branch(c.isa(descriptor=role, role=role_test))
                c.block("hit")
                c.payload(member=member)
                c.finish_pair()
                self.assert_safe(c, safe)

    def test_function_payloads_need_their_own_dyntype(self):
        for descriptor, safe in (("@dtf.0", True), ("@dtf.1", False)):
            with self.subTest(descriptor=descriptor):
                c = Case()
                c.dyntype("@dtf.0", kind=9)
                c.dyntype("@dtf.1", kind=9)
                c.g.dynfnt["fn[f:a]"] = "@dtf.0"
                c.g.dynfnt["fn[f:b]"] = "@dtf.1"
                c.branch(self.exact(c, descriptor))
                c.block("hit")
                c.payload(member="fn[f:a]")
                c.finish_pair()
                self.assert_safe(c, safe)

    def test_a_payload_type_no_dyntype_holds_is_rejected(self):
        c = self.classes()
        c.branch(self.exact(c, "@dt.Base"))
        c.block("hit")
        c.payload(member="Box")
        c.finish_pair()
        bad = c.proof().bad
        self.assertEqual(bad, ["dyn.payload of Box needs tag none (no DynType holds it) for %a0"])

    def test_stock_verifier_names_a_class_reads_tags(self):
        c = self.classes()
        c.payload(member="Base")
        c.ret()
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            c.g.verify(c.fn, False)
        self.assertIn("dyn.payload of Base needs tag @dt.Base/@dt.Child for %a0", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
