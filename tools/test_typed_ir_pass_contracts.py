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
from src.pystachy_compiler.driver import runtime_ir
from src.pystachy_compiler.ir import FnInfo, IFn, Ins, Val
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXALL, FXBIT, RAWR
from src.pystachy_compiler.syntax import Node


def empty_function():
    fn = IFn(FnInfo("contracts", "@contracts", Node("def", "contracts", 1), ""))
    fn.blocks[0].code = [Ins("ret.none", "", "")]
    return fn


def append_global_write(fn):
    op = Ins("mem.store", "", "")
    op.a = [Val("@probe", "*int"), Val("1", "int")]
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

def is_colon(text: str, pos: int) -> bool:
    c = text[pos]
    return c == ":"

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

print(summed([0.5, 1.5]), looked_up({"x": 2}, "x"), is_colon(":", 0))
print(accumulated([0.5, 1.5]), repeated(Box(3)), repeated(None))
"""


class PassContractTests(unittest.TestCase):
    def test_effect_safety_bounds_need_not_be_exact_or_solved(self):
        # FXALL is a sound bound even before EffectSummaries has been populated.
        # A stale, more precise upper bound also remains valid after an effect goes.
        for effects, writes in ((FXALL, True), (FXBIT["wG"] | FXBIT["R"], True),
                                (FXBIT["wG"], False)):
            with self.subTest(effects=effects, writes=writes):
                g, fn = Gen(), empty_function()
                fn.fx = effects
                if writes:
                    append_global_write(fn)
                with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                        patch.object(Gen, "verify") as verify:
                    self.assertEqual(g.optimize(fn, {"listget": True}), 0)
                self.assertEqual(g.summaries.fx, [])
                verify.assert_not_called()  # no rewrite, so no verifier rerun

    def test_missing_effect_is_rejected_before_pass(self):
        g, fn = Gen(), empty_function()
        append_global_write(fn)
        fn.fx = 0
        err = StringIO()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                patch.object(Gen, "listget") as run, redirect_stderr(err), \
                self.assertRaises(SystemExit):
            g.optimize(fn, {"listget": True})
        run.assert_not_called()
        self.assertIn("listget requires conservative effect safety bounds", err.getvalue())

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
            append_global_write(fn)
            return 1

        for rewrite, message in ((break_ir, "unknown op unknown.op"),
                                 (add_effect, "conservative effect safety bounds")):
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

    def test_unionslots_still_rejects_every_new_non_read_effect(self):
        # Invalidate read summaries without admitting mutation, exceptions,
        # callbacks, allocation/GC or runtime-state changes. A callee's summary
        # can conservatively have any one of these bits; unknown callbacks have all.
        for effect in ("R", "A", "U", "I", "wL", "wD", "wO", "wG", "wF"):
            with self.subTest(effect=effect):
                g, fn, callee = Gen(), empty_function(), empty_function()
                fn.fx = 0
                callee.f.ll = "@effect"
                callee.fx = FXALL if effect == "U" else FXBIT[effect]
                g.fll[callee.f.ll] = 0
                g.fns.append(callee)

                def add_call(gen, fn):
                    fn.blocks[0].code.insert(0, Ins("call", "None", "@effect"))
                    return 1

                err = StringIO()
                with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1"}), \
                        patch.object(Gen, "unionslots", add_call), \
                        patch.object(Gen, "nullcheck") as next_pass, \
                        redirect_stderr(err), self.assertRaises(SystemExit):
                    g.optimize(fn, {"unionslots": True, "nullcheck": True})
                next_pass.assert_not_called()
                self.assertIn("unionslots requires conservative effect safety bounds", err.getvalue())

    def test_returned_union_boxes_can_introduce_read_effects(self):
        # Decomposing the box returned by half() introduces union.tag/raw reads.
        # Their conservative rL/rD/rO classification exceeds calls()'s original
        # R/A summary, without changing the program's observable effects.
        path = Path(__file__).resolve().parent.parent / "tests/programs/inference/union_slots.py"
        source = path.read_text()
        decomposed = []
        original = Gen.unionslots

        def observe(gen, fn):
            changed = original(gen, fn)
            if fn.f.ll == "@f.calls":
                added, operations = 0, set()
                for block in fn.blocks:
                    for op in block.code:
                        extra = gen.opfx(op, fn.fa) & ~fn.fx
                        if extra:
                            added |= extra
                            operations.add(op.op)
                decomposed.append((changed, added, operations))
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}), \
                patch.object(Gen, "unionslots", observe):
            checked_ir = Gen().program(Loader([]).program(str(path), source))
        self.assertEqual(len(decomposed), 1)
        changed, added, operations = decomposed[0]
        self.assertGreater(changed, 0)
        self.assertEqual(added, RAWR)
        self.assertEqual(operations, {"union.tag", "union.raw"})
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}):
            normal_ir = Gen().program(Loader([]).program(str(path), source))
        self.assertEqual(checked_ir, normal_ir)

    def test_normal_dispatch_does_not_scan_contracts(self):
        g, fn = Gen(), empty_function()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0"}), \
                patch.object(optimizations, "gen_pass_check") as check:
            self.assertEqual(g.optimize(fn, {"listget": True}), 0)
        check.assert_not_called()

    def test_private_character_keeps_only_its_indexed_read_and_ascii_predicates(self):
        source = Path(__file__).resolve().parents[1] / "tests/programs/optimizations/opt_charslots.py"
        shapes = {}
        charslots = Gen.charslots

        def observe(gen, fn):
            changed = charslots(gen, fn)
            ops = [op for block in fn.blocks for op in block.code]
            points = {f"%t{op.r[0]}" for op in ops if op.op == "rt" and op.s == "text.ord_at"}
            shapes[fn.f.name] = (
                changed,
                [op.s for op in ops if op.op == "rt" and op.s in ("text.get", "text.ord_at")],
                {op.a[1].v for op in ops if op.op == "num.cmp" and op.s == "==" and op.a[0].v in points},
            )
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "charslots", observe):
            Gen().program(Loader([]).program(str(source), source.read_bytes().decode("latin1")))
        self.assertEqual(shapes["classify"], (1, ["text.ord_at"], {"0", "58"}))
        self.assertEqual(shapes["ordered"][:2], (1, ["text.ord_at"]))
        for name in ("returned", "boxed", "same_object", "nonascii", "assigned_twice", "conditional"):
            with self.subTest(name=name):
                self.assertEqual(shapes[name][:2], (0, ["text.get"]))

    def test_range_list_loads_require_invariant_list_and_index(self):
        root = Path(__file__).resolve().parents[1]
        fixtures = [root / "tests/ir/range_listget.py",
                    root / "tests/programs/optimizations/opt_listget_range.py"]
        shapes = {}
        original = Gen.listget

        def observe(gen, fn):
            changed = original(gen, fn)
            ops = [op for block in fn.blocks for op in block.code]
            shapes[fn.f.name] = (changed, sum(op.op == "rt" and op.s == "list.get" for op in ops))
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "listget", observe):
            for path in fixtures:
                Gen().program(Loader([]).program(str(path), path.read_text()))
        for name in ("tail", "stride", "captured", "entry_rebound", "stepped"):
            with self.subTest(name=name):
                self.assertEqual(shapes[name], (1, 0))
        for name in ("unknown_start", "changed_index", "different_list", "negative", "descending",
                     "shrink_before", "shrink_after", "alias_shrink", "captured_shrink",
                     "rebound_loop", "rebound_capture", "target_reassigned", "nested_target",
                     "callback", "suspended"):
            with self.subTest(name=name):
                self.assertEqual(shapes[name], (0, 1))
        # The inner loop proves its own index. Reaching the outer index would
        # require carrying the proof across the inner loop's back edge.
        self.assertEqual(shapes["nested"], (1, 1))

        shapes.clear()
        source = fixtures[0].read_text()
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "listget", observe):
            runtime_ir(str(fixtures[0]), source, False)
        for name in ("tail", "stride", "captured", "entry_rebound"):
            with self.subTest(runtime=name):
                self.assertEqual(shapes[name], (1, 0))
        for name in ("unknown_start", "changed_index", "different_list"):
            with self.subTest(runtime=name):
                self.assertEqual(shapes[name], (0, 1))

    def test_real_rewrites_are_verified_and_llvm_is_unchanged(self):
        events = []
        original_verify = Gen.verify

        def checked(gen, fn, eh):
            events.append(("verify-eh" if eh else "verify", fn.f.ll))
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

        # program() verifies the original IR and each changed pass verifies its
        # output. Two consecutive checks on the same function inspect the same IR.
        for previous, current in zip(events, events[1:]):
            if previous[0] == "verify":
                self.assertNotEqual(previous, current)
        rewritten = set()
        for j, event in enumerate(events):
            if event[0] not in ("verify", "verify-eh") and event[2] > 0:
                rewritten.add(event[0])
                self.assertEqual(events[j + 1], ("verify", event[1]))
        self.assertEqual(rewritten, {"charslots", "listget", "dictfuse", "unionslots", "nullcheck"})
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}):
            normal_ir = Gen().program(Loader([]).program("pass_contracts.py", SOURCE))
        self.assertEqual(checked_ir, normal_ir)


if __name__ == "__main__":
    unittest.main()
