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
from src.pystachy_compiler.ir import IFn, Ins, Val, cast_number, one_num, slot_register
from src.pystachy_compiler.symbols import FnInfo
from src.pystachy_compiler.loader import Loader
from src.pystachy_compiler.specs import FXALL, FXBIT, RAWR, REACH
from src.pystachy_compiler.syntax import Node


def empty_function():
    fn = IFn(FnInfo("contracts", "@contracts", Node("def", "contracts", 1), ""))
    fn.blocks[0].code = [Ins("ret.none", "", "")]
    return fn


def append_global_write(fn):
    op = Ins("mem.store", "", "")
    op.a = [Val("@probe", "&int"), Val("1", "int")]
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

def dotted(a: list[float], b: list[float]) -> float:
    total = 0.0
    for i in range(len(a)):
        total += a[i] * b[i]
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

print(summed([0.5, 1.5]), dotted([0.5, 1.5], [2.0, 4.0]), looked_up({"x": 2}, "x"), is_colon(":", 0))
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
        self.assertEqual(rewritten, {"charslots", "listget", "listguard", "dictfuse", "unionslots", "nullcheck"})
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0", "PYSTACHY_OPT": "",
                                    "PYSTACHY_IRFX": "0"}):
            normal_ir = Gen().program(Loader([]).program("pass_contracts.py", SOURCE))
        self.assertEqual(checked_ir, normal_ir)

    def test_listguard_folded_reads_trigger_post_pass_verification(self):
        source = """
def conditional(xs: list[int], n: int, take: bool) -> int:
    total = 0
    for i in range(n):
        if take:
            total += xs[i]
    return total
print(conditional([2, 3], 2, True))
"""
        changes, checked = [], []
        original_guard, original_check = Gen.listguard, optimizations.gen_pass_check

        def guard(gen, fn):
            before = len(fn.blocks)
            count = original_guard(gen, fn)
            if fn.f.name == "conditional":
                changes.append((count, len(fn.blocks) > before))
            return count

        def check(gen, fn, contract, after):
            if fn.f.name == "conditional" and contract.name == "listguard" and after:
                checked.append(True)
            return original_check(gen, fn, contract, after)

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "listguard", guard), \
                patch.object(optimizations, "gen_pass_check", check):
            Gen().program(Loader([]).program("folded_reads.py", source))
        self.assertEqual(len(changes), 1)
        self.assertTrue(changes[0][1])
        self.assertGreater(changes[0][0], 0)
        self.assertEqual(checked, [True])

    def test_listguard_preserves_copied_field_write_effects(self):
        source = """
class Box:
    def __init__(self) -> None:
        self.value = 0
def copy(xs: list[int], ys: list[int], box: Box, n: int) -> None:
    for i in range(n):
        box.value = xs[i]
        ys[i] = box.value
box = Box()
ys = [0, 0]
copy([3, 4], ys, box, 2)
print(ys, box.value)
"""
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}):
            checked = Gen().program(Loader([]).program("guarded_fields.py", source))
        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "0", "PYSTACHY_OPT": ""}):
            normal = Gen().program(Loader([]).program("guarded_fields.py", source))
        self.assertEqual(checked, normal)


def unused_casts(fn, n):
    # n casts that nothing reads, numbered as a pass numbers the casts it adds (ir.cast_number)
    added = []
    for _ in range(n):
        cast = Ins("cast", "int", "bits")
        cast.a = [Val("0", "%slot")]
        cast.r = one_num(cast_number(fn))
        added.append(cast)
    return added


def drop(fn, added):
    # fn without the casts added, whose numbers stay in IFn.casts, as a dropped cast's do
    gone = {id(cast) for cast in added}
    for block in fn.blocks:
        block.code = [i for i in block.code if id(i) not in gone]


def reaching_walk(gen, fn, slot):
    # the ops that Gen.reaching walks over from the last load of slot back to the load or store
    # of it before: how many, and how many of them are no cast
    preds = gen.preds(fn)
    loads = [(j, x) for j in range(len(fn.blocks)) for x in range(len(fn.blocks[j].code))
             if fn.blocks[j].code[x].op == "mem.load" and fn.blocks[j].code[x].a[0].v == slot]
    j, x = loads[-1]
    walked = []
    while True:
        code = fn.blocks[j].code
        for y in range(x - 1, -1, -1):
            walked.append(code[y])
            if code[y].op in ("mem.load", "mem.store") and code[y].a[0].v == slot:
                return len(walked), len([i for i in walked if i.op != "cast"])
        [j] = preds[fn.blocks[j].label]
        x = len(fn.blocks[j].code)


FUSED = """
def looked_up(d: dict[str, int], key: str) -> int:
    if key in d:
        return d[key]
    return -1


print(looked_up({"x": 2}, "x"))
"""


class CastBudgetTests(unittest.TestCase):
    """A cast touches no memory and lowering erases it: it counts toward no pass's budget, so that
    a pass decides as it would had the frontend made no cast (docs/typed-ir.md#casts)."""

    def lookups(self, source, name, casts=0):
        # The dict ops of function name of source once dictfuse has run on it, and how many it
        # rewrote, with casts unused casts put before the ops of the block of its last
        # dict.getitem (between that lookup and those before it); and the walk of Gen.reaching
        # there from the last load of its dict d (reaching_walk)
        found = []
        dictfuse = Gen.dictfuse

        def observe(gen, fn):
            if fn.f.name != name:
                return dictfuse(gen, fn)
            added = unused_casts(fn, casts)
            last = max(j for j in range(len(fn.blocks)) if any(i.op == "rt" and i.s == "dict.getitem" for i in fn.blocks[j].code))
            fn.blocks[last].code[0:0] = added
            walk = reaching_walk(gen, fn, [slot_register(s) for s in fn.slots if s.s == "d" and s.k == 0][0])
            changed = dictfuse(gen, fn)
            drop(fn, added)
            found.append((changed, [i.s for b in fn.blocks for i in b.code if i.op == "rt" and i.s.startswith("dict.")], walk))
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "dictfuse", observe):
            Gen().program(Loader([]).program(name + ".py", source))
        self.assertEqual(len(found), 1)
        return found[0]

    def test_lookups_that_casts_separate_are_fused(self):
        # (the lookup's dict and key are what a lookup twice REACH casts before it read: it reuses
        # that lookup's entry, as with no cast between them)
        changed, plain, _ = self.lookups(FUSED, "looked_up")
        self.assertGreater(changed, 0)
        self.assertEqual(self.lookups(FUSED, "looked_up", 2 * REACH)[:2], (changed, plain))

    def test_lookups_that_a_run_of_casts_separates_are_fused(self):
        # (xs.index(v) of a float v in a list of ints makes two bits casts, slot_word's: fourteen of
        # them put more than REACH ops between the loads of d of the two d["k"], fewer once the casts
        # are left out, as without casts: the second reuses the first's entry)
        source = ("def f(d: dict[str, int], xs: list[int], v: float) -> int:\n    a = d[\"k\"]\n    t = 0\n"
                  + "    t += xs.index(v)\n" * 14 + "    b = d[\"k\"]\n    return a + b + t\n\n\nprint(f({\"k\": 1}, [1, 2, 3], 2.0))\n")
        changed, ops, walk = self.lookups(source, "f")
        if not walk[1] <= REACH < walk[0]:
            self.skipTest(f"the walk passes {walk[0]} ops, {walk[1]} of them no cast: the casts no longer decide")
        self.assertEqual((ops.count("dict.getitem"), ops.count("dict.entry")), (0, 1))

    def test_charslots_counts_no_operand_of_a_cast(self):
        # (classify's character slot is rewritten as with no cast, with more unused casts than the
        # 4096 operands that the pass reads before it gives up)
        source = Path(__file__).resolve().parents[1] / "tests/programs/optimizations/opt_charslots.py"
        found = []
        charslots = Gen.charslots

        def observe(gen, fn):
            if fn.f.name != "classify":
                return charslots(gen, fn)
            added = unused_casts(fn, 4097)
            last = fn.blocks[len(fn.blocks) - 1].code
            last[len(last) - 1:len(last) - 1] = added
            changed = charslots(gen, fn)
            drop(fn, added)
            found.append(changed)
            return changed

        with patch.dict(os.environ, {"PYSTACHY_IRCHECK": "1", "PYSTACHY_OPT": ""}), \
                patch.object(Gen, "charslots", observe):
            Gen().program(Loader([]).program(str(source), source.read_bytes().decode("latin1")))
        self.assertEqual(found, [1])


if __name__ == "__main__":
    unittest.main()
