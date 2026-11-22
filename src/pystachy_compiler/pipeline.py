"""Attempt-owned compiler stages, from declarations to consumed typed IR.

Preparation and discovery still combine semantic typing, representation choices
and specialization. The finalized typed program is a real boundary: lowering is
an explicit, consuming operation. This does not make Gen reusable or concurrent.
"""
from __future__ import annotations
import os
import sys
from src.pystachy_compiler.callbacks import specialize_callbacks
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import NOLABELS, NONUMS, NOVALS, one_nums_intact
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import RENAMED
from src.pystachy_compiler.optimizations import call_counts
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import fxs, timing_end, timing_start


STAGE_PREDECESSORS: dict[str, str] = {
    "prepare": "new",
    "discover": "prepare",
    "analyze": "discover",
    "optimize": "analyze",
    "finalize": "optimize",
    "lower": "finalize",
}


class PipelineState:
    # One per Gen, outside Frame/save/restore/dry: only the attempt's top-level
    # orchestration advances it. Rejoin constructs a fresh Loader and Gen.
    def __init__(self):
        self.stage = "new"
        self.active = ""
        self.history: list[str] = []
        self.checks = False
        self.dump = False

    def begin(self, name: str) -> None:
        if name not in STAGE_PREDECESSORS:
            fail(f"internal error: unknown compiler stage {name}", 0)
        if self.active != "" or self.stage != STAGE_PREDECESSORS[name]:
            fail(f"internal error: compiler stage {name} requires completed {STAGE_PREDECESSORS[name]} (completed {self.stage}, active {self.active or 'none'})", 0)
        # An exception or retry leaves active set. Partially mutated state cannot
        # be resumed, finalized or lowered by a later stage call.
        self.active = name

    def complete(self, name: str) -> None:
        if name not in STAGE_PREDECESSORS:
            fail(f"internal error: unknown compiler stage {name}", 0)
        if self.active != name or self.stage != STAGE_PREDECESSORS[name]:
            fail(f"internal error: compiler stage {name} is not active", 0)
        self.stage = name
        self.history.append(name)
        self.active = ""


class PreparedProgram:
    # These are borrowed mutable ASTs, not a reusable/serializable semantic IR.
    # The owner check prevents declarations prepared by one attempt being used
    # with another attempt's classes, inference state or specialization caches.
    def __init__(self, owner: PipelineState, modules: list[Mod], tops: list[list[Node]]):
        self.owner = owner
        self.modules = modules
        self.tops = tops


def gen_typed_program(self, mods: list[Mod]) -> None:
    prepared = self.prepare_program(mods)
    self.discover_program(prepared)
    self.analyze_program()
    self.optimize_program()
    self.finalize_program()


def gen_program(self, mods: list[Mod]) -> str:
    self.typed_program(mods)
    return self.lower_program()


def gen_analyze_program(self) -> None:
    self.pipeline.begin("analyze")
    phase = "runtime" if self.rtmode else "program"
    started = timing_start()
    # The completed adapter set makes candidate discovery independent of which
    # caller first compiled a kernel. Versions add no frontend inference state.
    if not self.rtmode and "callbacks" in self.opts:
        specialize_callbacks(self.fns, self.adapters, self.cvos)
    # the whole program is built: its functions are printed in the order they were completed
    for j in range(len(self.fns)):
        self.fll[self.fns[j].f.ll] = j
    if len(NONUMS) + len(NOVALS) + len(NOLABELS) > 0:
        fail("internal error: an op changed the lists all ops start with", 0)
    self.pipeline.checks = os.getenv("PYSTACHY_IRCHECK", "") == "1"
    chk = self.pipeline.checks
    self.pipeline.dump = os.getenv("PYSTACHY_IRFX", "") == "1" and not self.rtcache
    dump = self.pipeline.dump
    on = self.opts
    if self.eh or len(on) > 0 or chk or dump or not self.rtmode:
        # the passes and eh_ir read the effect summaries (eh_ir: which calls may raise), and so
        # does the native depth policy, which is no optimization; the IR check computes them
        # too, so that the tests run effects even with every pass off
        self.effects()
    if not self.rtmode:
        # which source functions count toward the recursion limit (docs/internals.md#native-recursion-depth):
        # their guards' effects join the summaries before any pass or verification reads them
        self.recursionscope()
    if chk:
        # Union proofs distinguish read-only callees from calls that can invalidate
        # storage facts, so the first verification uses complete effect summaries too.
        for fn in self.fns:
            self.verify(fn, False)
    timing_end(phase + ".analysis", started)
    self.pipeline.complete("analyze")


def gen_optimize_program(self) -> None:
    self.pipeline.begin("optimize")
    phase = "runtime" if self.rtmode else "program"
    on = self.opts
    dump = self.pipeline.dump
    started = timing_start()
    if len(on) > 0:
        # (before eh_ir: a block that a try statement covers keeps its exception edge to the
        # landing block, Blk.handler, which the passes count, see preds)
        if "listguard" in on:
            self.callsites = call_counts(self.fns)
        changed = False
        for fn in self.fns:
            if self.optimize(fn, on) > 0:
                changed = True  # optimize verifies each changed pass when checks are enabled
        if changed and dump:
            self.effects()  # (what the passes left: tests/ir/*.fx pin them)
    timing_end(phase + ".optimize", started)
    self.pipeline.complete("optimize")


def gen_finalize_program(self) -> None:
    self.pipeline.begin("finalize")
    phase = "runtime" if self.rtmode else "program"
    on = self.opts
    chk = self.pipeline.checks
    dump = self.pipeline.dump
    started = timing_start()
    for fn in self.fns if self.eh else self.fns[:0]:
        if len(fn.tries) > 0:
            self.eh_ir(fn)
            if chk:
                self.verify(fn, True)
    if dump:
        for fn in self.fns:
            print(f"{fn.f.ll}: {fxs(fn.fx)}".rstrip(), file=sys.stderr)
    if "tupleret" in on:
        self.tuple_rets()  # (which functions return their tuples' slots by value: lowering reads it)
    # Admission belongs to the retained program boundary. The backend may consume
    # bodies only after runtime/extension export contracts have been checked.
    self.validate_module()
    # (then the key kinds of holes, which lowering reads as tables rather than asking the
    # frontend, after admission's errors as before: tools/typed_ir_text.py prints the boundary)
    self.key_kinds()
    if chk and not one_nums_intact():
        fail("internal error: an op changed the shared list of its number (one_num)", 0)
    timing_end(phase + ".finalize", started)
    self.pipeline.complete("finalize")


def gen_lower_program(self) -> str:
    self.pipeline.begin("lower")
    phase = "runtime" if self.rtmode else "program"
    started = timing_start()
    for fn in self.fns:
        self.lower(fn)
        # its LLVM text is all that is left to print: its IR goes (its summary, IFn.fx, stays)
        fn.blocks = []
        fn.slots = []
        fn.loops = []
        fn.cold = {}
        fn.fa = {}
    for op in ["eq", "cmp", "repr"] if not self.rtmode else []:
        self.dispatch(op)  # (each program defines them: runtime.py calls them like runtime.c)
    ir = self.lower_module()
    timing_end(phase + ".lower", started)
    if not one_nums_intact():
        fail("internal error: an op changed the shared list of its number (one_num)", 0)
    RENAMED.clear()  # (the program's classes': runtime.py, which the driver may compile next, has none)
    self.pipeline.complete("lower")
    return ir
