"""Context reuse, conservative unknown calls, and incremental effect fixed points.

Run with python3 -m unittest discover -s tools -p test_function_summaries.py.
The random graph oracle deliberately uses the previous whole-graph algorithm.
"""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins
from src.pystachy_compiler.ircheck import EffectSummaries
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXALL, FXBIT
from src.pystachy_compiler.syntax import Node


def oracle(direct, calls):
    fx = list(direct)
    changed = True
    while changed:
        changed = False
        for j, callees in enumerate(calls):
            m = fx[j]
            for c in callees:
                m |= fx[c]
            if m != fx[j]:
                fx[j] = m
                changed = True
    return fx


class EffectSummaryTests(unittest.TestCase):
    def test_empty_graph_and_no_return_bit(self):
        summaries = EffectSummaries()
        summaries.update([], [])
        self.assertEqual(summaries.fx, [])
        self.assertEqual(summaries.edge_visits, 0)
        summaries.update([FXBIT["N"], FXBIT["R"] | FXBIT["N"]], [[1], []])
        self.assertEqual(summaries.fx, [FXBIT["R"], FXBIT["R"]])
        summaries.update([], [])
        self.assertEqual(summaries.fx, [])

    def test_long_chain_and_unchanged_contexts(self):
        # Adverse order for a whole-graph scan: one new caller per full traversal.
        n = 5000
        calls = [[j + 1] for j in range(n - 1)] + [[], []]
        direct = [0] * (n - 1) + [FXBIT["wD"], 0]
        summaries = EffectSummaries()
        summaries.update(direct, calls)
        self.assertEqual(summaries.fx, [FXBIT["wD"]] * n + [0])
        self.assertEqual(summaries.edge_visits, n - 1)
        self.assertLessEqual(summaries.edge_visits, summaries.edge_bound)
        summaries.update(direct, calls)
        self.assertEqual(summaries.reused, n + 1)
        self.assertEqual(summaries.edge_visits, 0)
        # Mutating the caller's old input cannot mutate the retained snapshot.
        direct[n - 1] = FXBIT["rL"]
        summaries.update(direct, calls)
        self.assertEqual(summaries.fx, [FXBIT["rL"]] * n + [0])
        self.assertEqual(summaries.reused, 1)
        self.assertEqual(summaries.edge_visits, n - 1)

    def test_removed_cycle_effect_and_dependency(self):
        summaries = EffectSummaries()
        calls = [[1], [2], [1], []]
        summaries.update([0, 0, FXBIT["I"], FXALL], calls)
        self.assertEqual(summaries.fx, [FXBIT["I"]] * 3 + [FXALL])
        summaries.update([0, 0, 0, FXALL], calls)
        self.assertEqual(summaries.fx, [0, 0, 0, FXALL])
        self.assertEqual(summaries.reused, 1)
        calls[2].append(3)
        summaries.update([0, 0, 0, FXALL], calls)
        self.assertEqual(summaries.fx, [FXALL] * 4)
        calls[2].remove(3)
        summaries.update([0, 0, 0, FXALL], calls)
        self.assertEqual(summaries.fx, [0, 0, 0, FXALL])

    def test_seed_from_unchanged_callee_and_resize(self):
        summaries = EffectSummaries()
        summaries.update([0, FXBIT["I"], FXBIT["R"]], [[], [], []])
        summaries.update([0, FXBIT["I"], FXBIT["R"]], [[1], [], []])
        self.assertEqual(summaries.fx, [FXBIT["I"], FXBIT["I"], FXBIT["R"]])
        self.assertEqual(summaries.reused, 2)
        summaries.update([0, FXBIT["R"]], [[1], []])
        self.assertEqual(summaries.fx, [FXBIT["R"]] * 2)
        self.assertEqual(summaries.reused, 0)

    def test_random_graph_updates_match_full_fixed_point(self):
        rng = random.Random(83)
        bits = [v for k, v in FXBIT.items() if k != "N"]
        for _ in range(40):
            n = rng.randrange(1, 45)
            direct = [rng.choice([0, FXALL] + bits) for _ in range(n)]
            calls = [rng.sample(range(n), rng.randrange(min(n, 5) + 1)) for _ in range(n)]
            summaries = EffectSummaries()
            for _ in range(12):
                summaries.update(direct, calls)
                self.assertEqual(summaries.fx, oracle(direct, calls))
                self.assertLessEqual(summaries.edge_visits, summaries.edge_bound)
                j = rng.randrange(n)
                direct[j] = rng.choice([0, FXALL] + bits)
                calls[j] = rng.sample(range(n), rng.randrange(min(n, 5) + 1))

    def test_ir_dependencies_deduplicate_and_unknown_calls_stay_top(self):
        g = Gen()
        for name in ("caller", "leaf", "indirect", "external", "initializer"):
            fn = IFn(FnInfo(name, "@f." + name, Node("def", name, 1), ""))
            g.fll[fn.f.ll] = len(g.fns)
            g.fns.append(fn)
        for _ in range(20):
            op = Ins("call", "None", "")
            op.s = "@f.leaf"
            g.fns[0].blocks[0].code.append(op)
        g.fns[2].blocks[0].code.append(Ins("icall", "None", ""))
        op = Ins("call", "None", "")
        op.s = "@unresolved.external"
        g.fns[3].blocks[0].code.append(op)
        g.fll["@init.example"] = 1
        for _ in range(20):
            op = Ins("init", "None", "")
            op.s = "example"
            g.fns[4].blocks[0].code.append(op)
        g.effects()
        self.assertEqual(g.summaries.calls[4], [1])
        self.assertEqual(g.summaries.calls[0], [1])
        self.assertEqual([fn.fx for fn in g.fns], [0, 0, FXALL, FXALL, 0])
        g.effects()
        self.assertEqual(g.summaries.reused, 5)

    def test_parameter_return_context_reuse(self):
        # The existing instance cache owns signatures/returns; the effect cache consumes
        # those same compiled contexts. Repeated calls must not create new contexts.
        source = ('def identity(x):\n    return x\n'
                  'print(identity(1))\nprint(identity(2))\n'
                  'print(identity("first"))\nprint(identity("second"))\n')
        g = Gen()
        g.program(Loader([]).program("summary_contexts.py", source))
        instances = g.funcs["identity"].insts
        self.assertEqual(set(instances), {"int", "str"})
        self.assertEqual({key: f.ret for key, f in instances.items()}, {"int": "int", "str": "str"})
        contexts = [fn for fn in g.fns if fn.f.name == "identity"]
        self.assertEqual(len(contexts), 2)
        self.assertEqual([fn.fx for fn in contexts], [0, 0])


if __name__ == "__main__":
    unittest.main()
