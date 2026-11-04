"""Function-pass requirements, local fact ownership and verifier boundaries.

Run with python3 -m unittest discover -s tools -p test_typed_ir_pass_contracts.py.
"""
from contextlib import ExitStack, redirect_stderr
from io import StringIO
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import optimizations
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXALL, FXBIT
from src.pystachy_compiler.syntax import Node


def empty_function():
    fn = IFn(FnInfo("contracts", "@contracts", Node("def", "contracts", 1), ""))
    fn.blocks[0].code = [Ins("ret.none", "", "")]
    return fn


def append_list_read(fn):
    op = Ins("list.len", "int", "")
    op.a = [Val("%a0", "list[int]")]
    op.r = [1]
    fn.n = 1
    fn.blocks[0].code.insert(0, op)


SOURCE = """
class Box:
    def __init__(self, value: int) -> None:
        self.value = value

def summed(xs: list[float]) -> float:
    total = 0.0
    for x in xs:
        total += x
    return total

def looked_up(d: dict[str, int], key: str) -> int:
    if key in d:
        return d[key]
    return -1

def accumulated(xs: list[float]) -> int | float:
    total: int | float = 0
    for x in xs:
        total += x
    return total

def repeated(box: Box | None) -> int:
    try:
        return box.value + box.value
    except AttributeError:
        return -1

print(summed([0.5, 1.5]), looked_up({"x": 2}, "x"))
print(accumulated([0.5, 1.5]), repeated(Box(3)), repeated(None))
"""


class PassContractTests(unittest.TestCase):
    def test_effect_bounds_need_not_be_exact_or_solved(self):
        # FXALL is a sound bound even before EffectSummaries has been populated.
        # A stale, more precise upper bound also remains valid after an effect goes.
        for effects, reads in ((FXALL, True), (FXBIT["rL"] | FXBIT["R"], True),
                               (FXBIT["rL"], False)):
            with self.subTest(effects=effects, reads=reads):
                g, fn = Gen(), empty_function()
                fn.fx = effects
                if reads:
                    append_list_read(fn)
                with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                        patch.object(Gen, "verify") as verify:
                    self.assertEqual(g.optimize(fn, {"listget": True}), 0)
                self.assertEqual(g.summaries.fx, [])
                verify.assert_not_called()  # no rewrite, so no verifier rerun

    def test_missing_effect_is_rejected_before_pass(self):
        g, fn = Gen(), empty_function()
        append_list_read(fn)
        fn.fx = 0
        err = StringIO()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                patch.object(Gen, "listget") as run, redirect_stderr(err), \
                self.assertRaises(SystemExit):
            g.optimize(fn, {"listget": True})
        run.assert_not_called()
        self.assertIn("listget requires conservative effect bounds", err.getvalue())

    def test_entry_depth_snapshot_does_not_require_io_effect(self):
        g, fn = Gen(), empty_function()
        g.runtime("pys_recursion_depth")
        op = Ins("rt", "int", "recursion.depth")
        op.r = [1]
        fn.blocks[0].code.insert(0, op)
        fn.n, fn.rdepth, fn.fx = 1, "%t1", 0
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}):
            self.assertEqual(g.optimize(fn, {"listget": True}), 0)

    def test_post_eh_ir_is_rejected_before_pass(self):
        for retained_pads in (True, False):
            with self.subTest(retained_pads=retained_pads):
                g, fn = Gen(), empty_function()
                fn.pads = retained_pads
                if not retained_pads:
                    invoke = Ins("call", "None", "@callee")
                    invoke.b = ["normal", "unwind"]
                    fn.blocks[0].code = [invoke]
                err = StringIO()
                with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                        patch.object(Gen, "listget") as run, redirect_stderr(err), \
                        self.assertRaises(SystemExit):
                    g.optimize(fn, {"listget": True})
                run.assert_not_called()
                self.assertIn("listget requires pre-EH IR", err.getvalue())

    def test_changed_pass_is_checked_before_the_next_pass(self):
        def break_ir(gen, fn):
            fn.blocks[0].code.insert(0, Ins("unknown.op", "", ""))
            return 1

        def add_effect(gen, fn):
            append_list_read(fn)
            return 1

        for rewrite, message in ((break_ir, "unknown op unknown.op"),
                                 (add_effect, "conservative effect bounds")):
            with self.subTest(rewrite=rewrite.__name__):
                g, fn = Gen(), empty_function()
                fn.fx = 0
                err = StringIO()
                with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                        patch.object(Gen, "listget", rewrite), \
                        patch.object(Gen, "dictfuse") as next_pass, \
                        redirect_stderr(err), self.assertRaises(SystemExit):
                    g.optimize(fn, {"dictfuse": True, "listget": True})
                next_pass.assert_not_called()
                self.assertIn(message, err.getvalue())

    def test_normal_dispatch_does_not_scan_contracts(self):
        g, fn = Gen(), empty_function()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0"}), \
                patch.object(optimizations, "gen_pass_check") as check:
            self.assertEqual(g.optimize(fn, {"listget": True}), 0)
        check.assert_not_called()

    def test_real_rewrites_are_verified_and_llvm_is_unchanged(self):
        events = []
        original_verify = Gen.verify

        def checked(gen, fn, eh):
            events.append(("verify", fn.f.ll))
            return original_verify(gen, fn, eh)

        def observe(name, original):
            def wrapped(gen, fn):
                changed = original(gen, fn)
                events.append((name, fn.f.ll, changed))
                return changed
            return wrapped

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}), ExitStack() as patches:
            patches.enter_context(patch.object(Gen, "verify", checked))
            for contract in optimizations.PASS_CONTRACTS:
                name = contract.name
                patches.enter_context(patch.object(Gen, name, observe(name, getattr(Gen, name))))
            checked_ir = Gen().program(Loader([]).program("pass_contracts.py", SOURCE))

        rewritten = set()
        for j, event in enumerate(events):
            if event[0] != "verify" and event[2] > 0:
                rewritten.add(event[0])
                self.assertEqual(events[j + 1], ("verify", event[1]))
        self.assertEqual(rewritten, {"listget", "dictfuse", "unionslots", "nullcheck"})
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}):
            normal_ir = Gen().program(Loader([]).program("pass_contracts.py", SOURCE))
        self.assertEqual(checked_ir, normal_ir)


if __name__ == "__main__":
    unittest.main()
