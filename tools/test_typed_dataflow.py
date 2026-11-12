"""Controls for the control-flow edges, liveness and worklist that typed-IR proofs share.

The IR here is built by hand and only analyzed; it is never lowered or executed.
"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pystachy_compiler import dynamic_proof, union_proof
from src.pystachy_compiler.dataflow import flow_targets, forward_fixpoint, live_values
from src.pystachy_compiler.dynamic_proof import DynamicProof, DynTypes
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Ins, Val
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.union_proof import UnionProof

U = "union[int,float]"


class Fn:
    """A function of named blocks; op() gives each result the next number."""

    def __init__(self, ptypes=("bool", "int", "int")):
        f = FnInfo("f", "@f", Node("def", "f", 1), "")
        f.ptypes = list(ptypes)
        f.params = ["p" + str(i) for i in range(len(f.ptypes))]
        self.fn = IFn(f)
        self.fn.ps = list(range(len(f.ptypes)))
        self.b = self.fn.blocks[0]

    def block(self, label, handler=""):
        self.b = Blk(label)
        self.b.handler = handler
        self.fn.blocks.append(self.b)

    def op(self, op, t="", s="", a=(), b=(), results=0, x=""):
        i = Ins(op, t, s)
        i.x = x
        i.a = [Val(*v) for v in a]
        i.b = list(b)
        i.r = list(range(self.fn.n + 1, self.fn.n + results + 1))
        self.fn.n += results
        self.b.code.append(i)
        return "%t" + str(i.r[-1]) if i.r else ""

    def positions(self):
        return {b.label: j for j, b in enumerate(self.fn.blocks)}


def diamond():
    # entry -> left | right -> join, whose phi takes a different value on each edge
    c = Fn()
    x = c.op("scalar.bin", "int", "add", [("%a1", "int"), ("1", "int")], results=1)
    y = c.op("scalar.bin", "int", "add", [("%a2", "int"), ("2", "int")], results=1)
    c.op("cbr", a=[("%a0", "bool")], b=["left", "right"])
    c.block("left")
    c.op("br", b=["join"])
    c.block("right")
    c.op("br", b=["join"])
    c.block("join")
    p = c.op("phi", "int", a=[(x, "int"), (y, "int")], b=["left", "right"], results=1)
    c.op("ret", a=[(p, "int")])
    return c, x, y, p


class Targets(unittest.TestCase):
    def test_terminator_labels_in_order(self):
        c = Fn()
        c.op("cbr", a=[("%a0", "bool")], b=["yes", "no"])
        self.assertEqual(flow_targets(c.fn, c.b), ["yes", "no"])

    def test_return_has_none(self):
        c = Fn()
        c.op("ret.none")
        self.assertEqual(flow_targets(c.fn, c.b), [])

    def test_handler_follows_the_terminator(self):
        c = Fn()
        c.block("body", handler="landing")
        c.op("br", b=["after"])
        self.assertEqual(flow_targets(c.fn, c.b), ["after", "landing"])

    def test_check_adds_its_cold_block_by_message_or_key(self):
        c = Fn()
        c.fn.cold = {"IndexError: list index out of range": "cold1", "handler|IndexError": "cold2"}
        c.op("check", s="IndexError: list index out of range", a=[("%a0", "bool")], b=["next"])
        self.assertEqual(flow_targets(c.fn, c.b), ["next", "cold1"])
        c.block("covered", handler="landing")
        c.op("check", s="IndexError: list index out of range", x="handler|IndexError", a=[("%a0", "bool")], b=["next"])
        self.assertEqual(flow_targets(c.fn, c.b), ["next", "landing", "cold2"])

    def test_check_without_a_cold_block_keeps_its_fallthrough(self):
        c = Fn()
        c.op("check", s="ValueError: none", a=[("%a0", "bool")], b=["next"])
        self.assertEqual(flow_targets(c.fn, c.b), ["next"])

    def test_invoke_gives_its_normal_and_unwind_edges(self):
        c = Fn()
        c.op("call", "None", "@g", b=["next", "landing"])
        self.assertEqual(flow_targets(c.fn, c.b), ["next", "landing"])


class Liveness(unittest.TestCase):
    def test_phi_operand_is_live_on_its_own_edge_only(self):
        c, x, y, p = diamond()
        live = live_values(c.fn, c.positions())
        self.assertEqual(live["entry"], {"%a0": True, "%a1": True, "%a2": True})
        self.assertEqual(live["left"], {x: True})
        self.assertEqual(live["right"], {y: True})
        # (facts are kept from after the join's phi, which the return then reads)
        self.assertEqual(live["join"], {p: True})

    def test_loop_carries_values_around_its_back_edge(self):
        c = Fn()
        step = c.op("scalar.bin", "int", "add", [("%a1", "int"), ("1", "int")], results=1)
        c.op("br", b=["head"])
        c.block("head")
        i = c.op("phi", "int", a=[("0", "int"), ("%t9", "int")], b=["entry", "body"], results=1)
        more = c.op("num.cmp", "bool", "<", [(i, "int"), ("%a2", "int")], results=1)
        c.op("cbr", a=[(more, "bool")], b=["body", "done"])
        c.block("body")
        c.fn.n = 8
        nxt = c.op("scalar.bin", "int", "add", [(i, "int"), (step, "int")], results=1)
        self.assertEqual(nxt, "%t9")
        c.op("br", b=["head"])
        c.block("done")
        c.op("ret", a=[(i, "int")])
        live = live_values(c.fn, c.positions())
        # step and the bound are read in the loop on every later iteration
        self.assertEqual(live["head"], {i: True, step: True, "%a2": True})
        self.assertEqual(live["body"], {i: True, step: True, "%a2": True})
        self.assertEqual(live["done"], {i: True})
        self.assertEqual(live["entry"], {"%a1": True, "%a2": True})

    def test_handler_and_cold_edges_keep_their_reads_live(self):
        c = Fn()
        c.fn.cold = {"E: m": "cold"}
        c.op("br", b=["body"])
        c.block("body", handler="landing")
        c.op("check", s="E: m", a=[("%a0", "bool")], b=["after"])
        c.block("after")
        c.op("ret.none")
        c.block("landing")
        c.op("ret", a=[("%a1", "int")])
        c.block("cold")
        c.op("ret", a=[("%a2", "int")])
        live = live_values(c.fn, c.positions())
        self.assertEqual(live["body"], {"%a0": True, "%a1": True, "%a2": True})
        self.assertEqual(live["after"], {})

    def test_value_defined_before_its_use_in_a_block_is_not_live_in(self):
        c = Fn()
        v = c.op("scalar.bin", "int", "add", [("%a1", "int"), ("1", "int")], results=1)
        c.op("ret", a=[(v, "int")])
        self.assertEqual(live_values(c.fn, c.positions()), {"entry": {"%a1": True}})

    def test_label_of_no_block_is_skipped(self):
        c = Fn()
        c.op("br", b=["missing"])
        self.assertEqual(live_values(c.fn, c.positions()), {"entry": {}})


class Recorder:
    """An analysis whose facts are one key, K: which blocks narrow or forget it is given."""

    def __init__(self, c, narrow=(), forget=(), dead=()):
        self.fn = c.fn
        self.blocks = c.positions()
        self.base = {}
        self.full = ["?", "x"]
        self.visits = 0
        self.narrowing = set(narrow)
        self.forgetting = set(forget)
        self.dead = set(dead)
        self.log = []

    def flow(self, b, s, targets, edges):
        self.log.append(("flow", b.label, s.dom("K")))
        if b.label in self.narrowing:
            s.narrow("K", ["x"])
        if b.label in self.forgetting:
            s.forget("K")
        for target in flow_targets(self.fn, b):
            edge = s.clone()
            if (b.label, target) in self.dead:
                edge.live = False
            targets.append(target)
            edges.append(edge)

    def edge(self, s, source, target):
        self.log.append(("edge", source, target))
        return s.clone()

    def transfer(self, s, i, label, checking):
        self.log.append(("check" if checking else "transfer", label, i.op, s.dom("K")))


class Worklist(unittest.TestCase):
    def flows(self, r):
        return [entry[1] for entry in r.log if entry[0] == "flow"]

    def test_diamond_visits_each_block_once_first_in_first_out(self):
        c, _, _, _ = diamond()
        r = Recorder(c)
        forward_fixpoint(r)
        self.assertEqual(self.flows(r), ["entry", "left", "right", "join"])
        self.assertEqual(r.visits, 4)
        self.assertEqual([e for e in r.log if e[0] == "edge"],
                         [("edge", "entry", "left"), ("edge", "entry", "right"), ("edge", "left", "join"), ("edge", "right", "join")])

    def test_join_takes_the_union_of_its_edges(self):
        c, _, _, _ = diamond()
        r = Recorder(c, narrow=["left"])
        forward_fixpoint(r)
        # left proved K is x; right did not, and its edge reaches the queued join before the visit
        self.assertEqual([e for e in r.log if e[0] == "flow" and e[1] == "join"], [("flow", "join", ["?", "x"])])

    def test_changed_starting_facts_queue_a_block_again(self):
        # entry (K: x) -> head -> body (forgets K) -> head, and head -> done
        c = Fn()
        c.op("br", b=["head"])
        c.block("head")
        c.op("cbr", a=[("%a0", "bool")], b=["body", "done"])
        c.block("body")
        c.op("br", b=["head"])
        c.block("done")
        c.op("ret.none")
        r = Recorder(c, narrow=["entry"], forget=["body"])
        forward_fixpoint(r)
        self.assertEqual(self.flows(r), ["entry", "head", "body", "done", "head", "body", "done"])
        self.assertEqual(r.visits, 7)
        # the report sees only the stable facts: the back edge's wider K at the loop head
        self.assertEqual([e for e in r.log if e[0] == "check"],
                         [("check", "entry", "br", ["?", "x"]), ("check", "head", "cbr", ["?", "x"]),
                          ("check", "body", "br", ["?", "x"]), ("check", "done", "ret.none", ["?", "x"])])

    def test_no_report_runs_before_the_last_visit(self):
        c, _, _, _ = diamond()
        r = Recorder(c)
        forward_fixpoint(r)
        kinds = [e[0] for e in r.log if e[0] in ("flow", "check")]
        # (one report for each op that is no phi: three in entry, one in each other block)
        self.assertEqual(kinds, ["flow"] * 4 + ["check"] * 6)

    def test_dead_edge_and_missing_target_reach_nothing(self):
        c = Fn()
        c.op("cbr", a=[("%a0", "bool")], b=["never", "missing"])
        c.block("never")
        c.op("ret.none")
        r = Recorder(c, dead=[("entry", "never")])
        forward_fixpoint(r)
        self.assertEqual(self.flows(r), ["entry"])
        self.assertEqual([e for e in r.log if e[0] == "edge"], [])
        self.assertEqual([e[1] for e in r.log if e[0] == "check"], ["entry"])

    def test_phis_are_left_to_the_edge(self):
        c, _, _, _ = diamond()
        r = Recorder(c)
        forward_fixpoint(r)
        self.assertNotIn("phi", [e[2] for e in r.log if e[0] == "check"])


class Proofs(unittest.TestCase):
    def union_guard(self):
        # if the box holds an int, read its payload; else return
        c = Fn(ptypes=(U,))
        tag = c.op("union.tag", "int", a=[("%a0", U)], results=1)
        hit = c.op("num.cmp", "bool", "==", [(tag, "int"), ("1", "int")], results=1)
        c.op("cbr", a=[(hit, "bool")], b=["read", "skip"])
        c.block("read")
        c.op("union.payload", "%slot", "int", [("%a0", U)], results=2)
        c.op("br", b=["skip"])
        c.block("skip")
        c.op("ret.none")
        return c

    def test_union_proof_uses_the_shared_liveness_and_worklist(self):
        c = self.union_guard()
        proof = UnionProof(c.fn, {"int": 1, "float": 2})
        self.assertEqual(proof.livevalues, live_values(c.fn, proof.blocks))
        with patch.object(union_proof, "forward_fixpoint") as shared:
            proof.run()
        shared.assert_called_once_with(proof)
        proof.run()
        self.assertEqual((proof.visits, proof.bad), (3, []))

    def test_union_proof_still_rejects_the_unguarded_read(self):
        c = self.union_guard()
        c.fn.blocks[0].code[-1].b = ["read", "read"]
        proof = UnionProof(c.fn, {"int": 1, "float": 2})
        proof.run()
        self.assertEqual(proof.badblocks, ["read"])

    def test_dynamic_proof_uses_the_shared_liveness_and_worklist(self):
        c = Fn(ptypes=("dyn",))
        tag = c.op("dyn.type", "dyntype", a=[("%a0", "dyn")], results=1)
        hit = c.op("ptr.cmp", "bool", "==", [(tag, "dyntype"), ("@pys_dyntype_int", "dyntype")], results=1)
        c.op("cbr", a=[(hit, "bool")], b=["read", "skip"])
        c.block("read")
        c.op("dyn.payload", "%slot", "int", [("%a0", "dyn")], results=2)
        c.op("br", b=["skip"])
        c.block("skip")
        c.op("ret.none")
        proof = DynamicProof(c.fn, DynTypes([], {}, {}))
        self.assertEqual(proof.livevalues, live_values(c.fn, proof.blocks))
        with patch.object(dynamic_proof, "forward_fixpoint") as shared:
            proof.run()
        shared.assert_called_once_with(proof)
        proof.run()
        self.assertEqual((proof.visits, proof.bad), (3, []))
        c.fn.blocks[0].code[-1].b = ["read", "read"]
        unguarded = DynamicProof(c.fn, DynTypes([], {}, {}))
        unguarded.run()
        self.assertEqual(unguarded.badblocks, ["read"])


if __name__ == "__main__":
    unittest.main()
