"""Dynamic-tag guard regressions over typed IR, without lowering unsafe IR."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pystachy_compiler.dynamic_proof import DynamicProof
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
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

    def proof(self):
        proof = DynamicProof(self.fn)
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

    def test_unsupported_payloads_do_not_claim_exact_builtin_proofs(self):
        for member in ("int", "Box", "list[int]"):
            c = Case()
            c.payload(member=member)
            c.ret()
            proof = c.proof()
            self.assertFalse(proof.bad)
            self.assertEqual(proof.payloads, 0)

    def test_stock_verifier_rejects_a_missing_dynamic_guard(self):
        c = Case()
        c.payload()
        c.ret()
        errors = StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit):
            c.g.verify(c.fn, False)
        self.assertIn("dyn.payload needs tag float", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
