#!/usr/bin/env python3
"""Inspect one real hosted compilation in an isolated worker (prototype).

This developer tool observes the existing compiler; it does not execute the source,
replace ``pystachy check``, or promise independent analysis of unreachable templates.
See docs/compiler-inspection.md for the versioned report and its limitations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import traceback


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
PASS_RULES = {
    "charslots": "Replace a singly defined private character with its code point when every read compares it to an ASCII literal.",
    "listget": "Replace a checked sequence-loop list read only when its index is in bounds and no intervening effect can shorten the list or run user code.",
    "listguard": "Copy an innermost range loop whose ops change no list's length, with unchecked item reads and assignments of lists it does not rebind at the index plus a constant, and run the copy only where tests of the lists' lengths before the loop prove every such index in bounds.",
    "dictfuse": "Reuse a known dictionary entry only while control flow, key equality and intervening effects preserve the lookup; mutation or user callbacks can invalidate it.",
    "unionslots": "Split eligible local union slots into tag/payload storage and reconstruct boxes at uses that require them.",
    "nullcheck": "Remove redundant null checks only where the existing control-flow proof establishes a non-null value.",
    "exceptions": "Lower retained exception regions using the compiler's conservative effect summaries.",
    "recursionscope": "The native depth policy, not a PYSTACHY_OPT pass: give checked entries and restorations to the source functions on a direct-call cycle or whose summary can run unseen code (U); the others keep an entry-depth snapshot only for their handlers. A cycle that reaches no U and nothing else that uses the depth (closed recursion) keeps its entries without restorations: lowering passes its depth as an argument.",
}
PROGRAM_PASS_UNITS = {
    "recursionscope": "counted source functions",
}
RECURSION_OPS = ("enter", "resume", "leave", "depth", "restore")
# Only compiler inputs are recorded, never arbitrary process environment values.
ENV_KEYS = (
    "PYSTACHY_HOME", "PYSTACHY_PATH", "PYSTACHY_OPT", "PYSTACHY_IRCHECK",
    "PYSTACHY_IRFX", "PYSTACHY_UNICODE_AUDIT",
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str | None:
    descriptor = None
    try:
        # Reports also run in the parent after a worker timeout. Never let a
        # FIFO or device block that recovery path. Check the opened descriptor
        # too: the path can change after stat, including a symlink's target.
        if not stat.S_ISREG(path.stat().st_mode):
            return None
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        hashed = hashlib.sha256()
        while data := os.read(descriptor, 1024 * 1024):
            hashed.update(data)
        return hashed.hexdigest()
    except OSError:
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def compiler_identity() -> dict:
    sources = [ROOT / "pystachy.py", ROOT / "VERSION", *sorted((ROOT / "src").rglob("*.py"))]
    manifest = [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in sources]
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    revision = None
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
        if git.returncode == 0:
            revision = git.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"hosted": True, "revision": revision, "source_sha256": fingerprint,
            "sources": manifest, "version": (ROOT / "VERSION").read_text().strip(),
            "python": platform.python_version(), "platform": platform.platform()}


def base_report(source: str, function: str, typed_after_only: bool = False) -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "status": "error",
        "compiler": compiler_identity(),
        "tool": {"path": "tools/inspect_compiler.py", "sha256": digest(Path(__file__))},
        "input": {"path": source, "sha256": digest(Path(source)), "modules": [],
                  "changed_during_compilation": False},
        "settings": {"environment": {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
                     | {"PYSTACHY_IRCHECK": "1"},
                     "function_filter": function, "command": "ir", "executes_program": False,
                     "forced_environment": {"PYSTACHY_IRCHECK": "1"},
                     "captures": "typed-after" if typed_after_only else "all"},
        "diagnostics": [], "attempts": [], "passes": [], "pass_contracts": {}, "program_passes": [],
        "stages": [{"name": name, "status": "unavailable", "artifact": None}
                   for name in ("typed-before", "typed-after", "llvm")],
        "verification": {"requested": True, "calls": 0, "completed": False,
                         "scope": "Pystachy typed IR; LLVM assembly and execution are not performed"},
        "artifacts": {},
        "limitations": [
            "Function-level source locations only; typed instructions currently carry no source spans.",
            "The frontend combines semantic analysis, specialization and IR construction.",
            "Pass rules describe general contracts, not exact reasons for every missed optimization.",
            "This is the first terminal error, not multi-error or all-units semantic checking.",
            "Snapshot IR and schema are experimental; this is a hosted developer tool.",
            "Dynamic boundary counts are static typed-IR observations, not runtime, allocation or minimal-containment proofs.",
        ],
    }


def tool_diagnostic(code: str, phase: str, message: str, source: str) -> dict:
    return {"code": code, "severity": "error", "phase": phase, "message": message,
            "file": source, "line": 0, "column": None, "context": []}


class Observer:
    """Read snapshots immediately: the compiler mutates ops and frees typed IR."""

    def __init__(self, report: dict, output: Path, function: str, typed_after_only: bool = False, guard_evidence: bool = False):
        from src.pystachy_compiler import diagnostics
        from src.pystachy_compiler.utils import fxs, typestr
        self.diagnostics = diagnostics
        self.fxs = fxs
        self.typestr = typestr
        self.report = report
        self.output = output
        self.function = function
        # (only the typed-after snapshot: no typed-before snapshot, pass records or diffs)
        self.typed_after_only = typed_after_only
        self.guard_evidence = guard_evidence
        self.nullcheck_evidence: list[dict] = []
        # The slots the unionslots pass split, by function object (kept alive with it, so that
        # an id is never another function's): each pair's tag and payload slots and the type of
        # the slot they replace, which the IR no longer names.
        self.split_unions: dict[int, tuple] = {}
        self.before: list[dict] = []
        self.after: list[dict] = []
        self.captured_before = False
        self.attempt: dict | None = None
        self.gen = None
        self.restores: list[tuple] = []
        self.source_reads: list[dict] = []
        # Hosted-only observations, keyed by the actual instruction object. A dry
        # run or a discarded/retried function can reuse its temporary names; those
        # instructions must not annotate the replacement function's values.
        self.representation_origins: dict[object, dict] = {}

    def selected(self, fn) -> bool:
        return not self.function or self.function in fn.f.ll or self.function in self.diagnostics.shown(fn.f.name)

    def location(self, line: int) -> dict:
        d = self.diagnostics
        file = d.FILES[line // d.LINES] if line >= d.LINES else d.SRC
        return {"file": file, "line": line % d.LINES if line >= d.LINES else line,
                "column": None, "precision": "function"}

    @staticmethod
    def instruction(ins) -> dict:
        return {"op": ins.op, "type": ins.t, "text": ins.s, "immediate": ins.k,
                "descriptor": ins.x, "results": list(ins.r),
                "operands": [{"value": a.v, "type": a.t} for a in ins.a],
                "targets": list(ins.b)}

    def snapshot(self, fn) -> dict:
        f = fn.f
        return {
            "symbol": f.ll, "name": self.diagnostics.shown(f.name), "location": self.location(f.node.line),
            "parameters": [{"name": name, "type": self.typestr(t), "representation": t}
                           for name, t in zip(f.params, f.ptypes, strict=True)],
            "return_type": self.typestr(f.ret), "return_representation": f.ret,
            "representation_metadata": self.representation_metadata(fn),
            "specialization": {"instantiated": f.inst, "generic": f.generic},
            "effects": self.fxs(fn.fx), "effects_scope": "last compiler analysis; may be conservative after rewrites",
            "recursion": {"counted": fn.counted, "rdepth": fn.rdepth, "landed": fn.landed, "gdepth": fn.gdepth,
                          "generator": f.gen, "coroutine": fn.coro},
            "slots": [self.instruction(i) for i in fn.slots],
            **({"split_unions": self.split_record(fn)} if self.guard_evidence else {}),
            # A check op raises from a separate block: its key (the op's descriptor, else its
            # text) -> that block's label.
            "check_targets": dict(fn.cold),
            "blocks": [{"label": b.label, "handler": b.handler,
                        "operations": [self.instruction(i) for i in b.code]} for b in fn.blocks],
            "loops": [{"kind": lp.kind, "mode": lp.mode, "head": lp.head, "body": lp.body,
                       "step": lp.step, "exit": lp.exit, "tests": list(lp.tests), "indices": list(lp.idx)}
                      for lp in fn.loops],
        }

    @staticmethod
    def representation_signature(ins) -> tuple:
        """Invalidate an observed origin if a subsequent pass rewrites its producer."""
        return (ins.op, ins.t, ins.s, ins.k, ins.x, tuple(ins.r),
                tuple((a.v, a.t) for a in ins.a))

    def record_representation(self, gen, value, representation: str, origin: str,
                              producer_ops=("slot.unpack", "rt", "invoke")) -> None:
        from src.pystachy_compiler.ir import tmpname
        from src.pystachy_compiler.utils import is_tuple, unopt
        if not is_tuple(unopt(representation)) or not value.v.startswith("%t"):
            return
        for block in reversed(gen.fn.blocks):
            for ins in reversed(block.code):
                if ins.r and value.v == tmpname(ins.r[-1]):
                    # Default hooks describe values just read from container storage.
                    # search_hold alone permits a newly created phi, whose read
                    # contract still needs proof for each incoming value.
                    if ins.op not in producer_ops:
                        return
                    entry = {"value": value.v, "representation": representation,
                             "origin": origin, "definition_type": ins.t,
                             "signature": self.representation_signature(ins)}
                    previous = self.representation_origins.get(ins)
                    if previous is not None and previous["representation"] != representation:
                        raise ValueError("conflicting observed container representations")
                    self.representation_origins[ins] = entry
                    return

    def clone_instruction_wrapper(self, original):
        def wrapped(source, numbers, labels):
            # The compiler's explicit cloning boundary supplies both actual
            # instruction objects. Never infer provenance from matching temp IDs
            # or types: discarded functions and dry runs may reuse either.
            observed = self.representation_origins.get(source)
            signature = self.representation_signature(source)
            target = original(source, numbers, labels)
            if observed is None or observed["signature"] != signature:
                return target
            if (target is source or target in self.representation_origins
                    or len(set(numbers.values())) != len(numbers)
                    or len(set(labels.values())) != len(labels)):
                return target

            def renamed(value):
                if value.startswith("%t") and value[2:].isdigit() and int(value[2:]) in numbers:
                    return "%t" + str(numbers[int(value[2:])])
                return value

            expected = (source.op, source.t, source.s, source.k, source.x,
                        tuple(numbers[r] for r in source.r),
                        tuple((renamed(a.v), a.t) for a in source.a))
            if (self.representation_signature(source) != signature
                    or self.representation_signature(target) != expected
                    or target.b != [labels.get(label, label) for label in source.b]):
                return target
            self.representation_origins[target] = dict(observed,
                value=renamed(observed["value"]), definition_type=target.t,
                signature=self.representation_signature(target))
            return target
        return wrapped

    def held_representation_wrapper(self, name: str):
        def decorate(original):
            def wrapped(gen, value, *args, **kwargs):
                from src.pystachy_compiler.bigints import held
                from src.pystachy_compiler.utils import is_opt, targs, unopt
                if name == "held_pair":
                    representation = "tuple[" + ",".join(held(t) for t in targs(value.t)) + "]"
                elif name == "held_read" and is_opt(value.t):
                    representation = "opt[" + held(unopt(value.t)) + "]"
                else:
                    representation = held(value.t)
                self.record_representation(gen, value, representation, name)
                return original(gen, value, *args, **kwargs)
            return wrapped
        return decorate

    def big_popitem_wrapper(self, original):
        def wrapped(gen, *args, **kwargs):
            value = original(gen, *args, **kwargs)
            self.record_representation(gen, value, value.t, "big_popitem")
            return value
        return wrapped

    def search_hold_wrapper(self, original):
        def wrapped(gen, value, element_type, container_type):
            from src.pystachy_compiler.bigints import search_type
            function, before = gen.fn, gen.n
            result = original(gen, value, element_type, container_type)
            representation = search_type(container_type, element_type)
            # search_hold's optional phi has a declared fixed-width type, but its
            # nonnull arm has just built a held-layout view. This is a phi contract
            # to prove on every incoming edge, not a fact about an arbitrary input
            # that the helper happened to return unchanged.
            if representation != element_type and gen.fn is function and result.v != value.v and \
                    result.v.startswith("%t") and result.v[2:].isdigit() and int(result.v[2:]) > before:
                self.record_representation(gen, result, representation, "search_hold", ("phi",))
            return result
        return wrapped

    def representation_metadata(self, fn) -> dict:
        """Export definition contracts separately from each operand's typed view.

        A promoting tuple view may alias a shorter plain tuple whose items are not
        the marker. These are read representations, not claims that all trailing
        slots exist. A checker must prove every view conversion and marker guard.
        """
        from src.pystachy_compiler.diagnostics import int_lists
        from src.pystachy_compiler.ir import tmpname
        from src.pystachy_compiler.utils import is_tuple, unopt
        sources = {}
        # All emitted tuple constants matter, not only source tuple displays in
        # tconstdata. Builtin constants are Data("tuple") records too; their
        # native item values are precisely what lower_data emits as slots.
        constants = {data.name: data for data in self.gen.consts if data.kind == "tuple"} if self.gen is not None else {}
        for index, representation in enumerate(fn.f.ptypes):
            if is_tuple(unopt(representation)):
                value = f"%a{index}"
                sources[value] = {"value": value, "representation": representation, "origin": "parameter"}
        operations = fn.slots + [ins for block in fn.blocks for ins in block.code]
        for ins in operations:
            if ins.r and is_tuple(unopt(ins.t)):
                value = f"%stk.{ins.r[0]}" if ins.op == "slot" and ins.k == 2 else tmpname(ins.r[-1])
                # A normal slot is an address, not the tuple held in that address.
                if ins.op != "slot" or ins.k == 2:
                    sources[value] = {"value": value, "representation": ins.t,
                                      "origin": "allocation" if ins.op == "alloc.fixed" or ins.op == "slot" else "definition",
                                      "definition_type": ins.t}
            observed = self.representation_origins.get(ins)
            if observed is not None and observed["signature"] == self.representation_signature(ins):
                sources[observed["value"]] = {key: value for key, value in observed.items() if key != "signature"}
            for operand in ins.a:
                constant = constants.get(operand.v)
                if constant is not None:
                    representation = constant.text or "tuple[" + ",".join(item.t for item in constant.items) + "]"
                    sources[operand.v] = {"value": operand.v, "representation": representation, "origin": "constant",
                                          "items": [{"value": item.v, "representation": item.t} for item in constant.items]}
        return {"version": 1, "int_containers": int_lists(),
                "scope": "definition and container-read representations; not physical allocation extents",
                "sources": [sources[value] for value in sorted(sources)]}

    @staticmethod
    def counts(snapshot: dict) -> dict:
        return dict(sorted(Counter(i["op"] + (":" + i["text"] if i["op"] == "rt" else "")
                                   for b in snapshot["blocks"] for i in b["operations"]).items()))

    @staticmethod
    def render(snapshot: dict) -> list[str]:
        # One instruction per line gives useful diffs even when operation counts agree.
        lines = [f"function {snapshot['symbol']} -> {snapshot['return_representation']}\n"]
        for slot in snapshot["slots"]:
            lines.append("  slot " + json.dumps(slot, sort_keys=True) + "\n")
        for block in snapshot["blocks"]:
            lines.append(f"{block['label']} handler={block['handler']}\n")
            lines.extend("  " + json.dumps(i, sort_keys=True) + "\n" for i in block["operations"])
        return lines

    def capture_before(self, gen) -> None:
        if not self.captured_before:
            if not self.typed_after_only:
                self.before = [self.snapshot(fn) for fn in gen.fns if self.selected(fn)]
            self.captured_before = True
            if self.attempt is not None:
                self.attempt["typed_functions"] = len(gen.fns)
                self.attempt["selected_functions"] = len(self.before)
                self.attempt["enabled_optimizations"] = list(gen.opts)
                footprint = self.attempt["dynamic_boundary"]["footprints"]["before"]
                footprint.update(status="partial", functions={fn.f.ll: self.boundary_function(gen, fn) for fn in gen.fns})

    @staticmethod
    def dynamic_types(gen) -> list[dict]:
        # Every DynType the program emits (dynamic.py: dyn_class_type, dyn_fn_type and generator
        # types), as lowered: a dynamic box's tag is the address of one of these or of a
        # runtime.c builtin. cls is the word class dispatchers switch on, base the DynType that
        # pys_dyn_isa follows, role a secondary base's, and payload the static type of the
        # value a box of it holds.
        from src.pystachy_compiler.dynamic import DF_ROLE
        held = {symbol: t for t, symbol in gen.dyntypes.items()}
        held.update({symbol: t for t, symbol in gen.dynfnt.items()})
        types = []
        for d in gen.consts:
            if d.kind == "dyntype":
                flags = int(d.items[2].v)
                types.append({"symbol": d.name, "kind": int(d.items[0].v), "cls": int(d.items[1].v),
                              "flags": flags, "base": "" if d.refs[2] == "null" else d.refs[2],
                              "role": d.refs[6] if flags & DF_ROLE and len(d.refs) == 7 else "",
                              "payload": held.get(d.name, "")})
        return sorted(types, key=lambda t: t["symbol"])

    @staticmethod
    def classes(gen) -> dict:
        # Each class of the program: its single base (a class of the program, a builtin
        # exception class or none) and its fieldless secondary base, which Gen.derives follows;
        # the unrelated classes whose objects it may also be (a primary chain's and a secondary
        # base's common subclass); and whether its objects begin with the class tag. An object of
        # one class is no object of a class related to it none of these ways: their fields are
        # other memory (Gen.disjoint).
        return {name: {"base": info.base, "role": info.role, "overlaps": sorted(info.overlaps),
                       "tagged": info.tag != 0} for name, info in sorted(gen.classes.items())}

    @staticmethod
    def key_descriptors(gen, functions) -> dict:
        # @s.N -> its text, for each string constant an operand of the snapshot passes as a key
        # kind (ptrtoint of its address) to a runtime function that makes a dict or a set
        found = {}
        for fn in functions:
            for block in fn["blocks"]:
                for op in block["operations"]:
                    for operand in op["operands"][:1]:
                        value = operand["value"]
                        if (op["op"] == "rt" and op["text"].startswith(("dict.", "set.")) and value.startswith("ptrtoint (ptr @s.")
                                and value.endswith(" to i64)")):
                            name = value[len("ptrtoint (ptr "):-len(" to i64)")]
                            number = name[3:]
                            if number.isdigit() and int(number) < len(gen.strvals):
                                found[name] = gen.strvals[int(number)]
        return dict(sorted(found.items()))

    @staticmethod
    def class_layouts(gen) -> dict:
        # Each class's struct as field.addr indexes it: its fields (a name beginning with a
        # space is hidden storage), then each "is assigned" flag (fl_fields) and identity box.
        # A field read tests its flag unless it has none or no read finds it unassigned
        # (fsure), which check_lean_fields.py's obligations rely on.
        return {name: {"fields": list(info.fields), "flags": dict(info.fflag), "sure": sorted(info.fsure)}
                for name, info in sorted(gen.classes.items())}

    @staticmethod
    def boundary_function(gen, fn) -> dict:
        operations, calls = Counter(), Counter()
        for block in fn.blocks:
            for ins in block.code:
                if ins.op.startswith("dyn."):
                    operations[ins.op] += 1
                if ins.op == "rt" and ins.s.startswith("dyn."):
                    calls[ins.s] += 1
        return {"name": fn.f.name, "module": gen.fn_home(fn.f),
                "tracks_numeric_identity": gen.fn_identity(fn.f),
                "dynamic_operations": dict(sorted(operations.items())),
                "dynamic_runtime_calls": dict(sorted(calls.items())),
                "numeric_companion_slots": sum(ins.op == "slot" and ins.t == "dyn" and ins.s.endswith(".box") for ins in fn.slots),
                "numeric_generation_slots": sum(ins.op == "slot" and ins.t == "int" and ins.s.endswith(".boxgen") for ins in fn.slots)}

    @staticmethod
    def boundary_totals(functions: dict) -> dict:
        operations, calls = Counter(), Counter()
        for function in functions.values():
            operations.update(function["dynamic_operations"])
            calls.update(function["dynamic_runtime_calls"])
        return {"functions": len(functions),
                "dynamic_operations": dict(sorted(operations.items())),
                "dynamic_runtime_calls": dict(sorted(calls.items())),
                "numeric_companion_slots": sum(fn["numeric_companion_slots"] for fn in functions.values()),
                "numeric_generation_slots": sum(fn["numeric_generation_slots"] for fn in functions.values())}

    def identity_wrapper(self, original):
        def wrapped(gen, modules, *args, **kwargs):
            result = original(gen, modules, *args, **kwargs)
            if self.attempt is not None:
                d = self.diagnostics
                paths = [{d.FILES[k].removeprefix("./") for k in flags}
                         for flags in (d.DYNFILES, d.INTFILES, d.IDINERT)]
                enabled = d.dynamic_program()
                observed = []
                for module in modules:
                    path = module.path.removeprefix("./")
                    observed.append({"name": module.name, "path": module.path,
                        "dependencies": sorted(module.deps),
                        "dynamic_any": path in paths[0], "promoting_int": path in paths[1],
                        "identity_inert_requested": path in paths[2],
                        "identity_inert_active": module.name in gen.idhint,
                        "tracks_numeric_identity": enabled and module.name not in gen.idoff})
                self.attempt["dynamic_boundary"].update(
                    policy_status="observed", modules=observed, dynamic_any_enabled=enabled,
                    full_graph_fallback=gen.idfull, hints_enabled=gen.idtry,
                    tracked_modules=[m["name"] for m in observed if m["tracks_numeric_identity"]])
            return result
        return wrapped

    def wrap(self, cls, name: str, wrapper) -> None:
        original = getattr(cls, name)
        self.restores.append((cls, name, original))
        setattr(cls, name, wrapper(original))

    def phase_wrapper(self, phase: str):
        def decorate(original):
            def wrapped(gen, *args, **kwargs):
                old = self.diagnostics.PHASE
                self.diagnostics.PHASE = phase
                result = original(gen, *args, **kwargs)
                self.diagnostics.PHASE = old
                return result
            return wrapped
        return decorate

    def parse_wrapper(self, original):
        def wrapped(loader, source, line, *args, **kwargs):
            # RAW's hosted latin-1 round trip preserves source bytes apart from
            # universal newline conversion performed by the compiler's text read.
            path = self.location(line)["file"]
            consumed = source.encode(self.diagnostics.RAW)
            try:
                observed = Path(path).read_bytes()
            except OSError:
                observed = None
            normalized = (observed.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                          if observed is not None else None)
            self.source_reads.append({
                "path": path, "sha256": hashlib.sha256(observed).hexdigest() if observed is not None else None,
                "source_sha256": hashlib.sha256(consumed).hexdigest(),
                "consumed_source_encoding": self.diagnostics.RAW + "; universal newlines",
                "changed_since_read": normalized != consumed,
            })
            old = self.diagnostics.PHASE
            self.diagnostics.PHASE = "parse"
            result = original(loader, source, line, *args, **kwargs)
            self.diagnostics.PHASE = old
            return result
        return wrapped

    def program_wrapper(self, original):
        def wrapped(gen, *args, **kwargs):
            from src.pystachy_compiler.diagnostics import NeedSliceEH, Rejoin
            self.before, self.after = [], []
            self.gen = gen
            self.captured_before = False
            self.attempt = {"index": len(self.report["attempts"]) + 1, "status": "failed",
                            "dynamic_boundary": {"policy_status": "unavailable", "modules": [],
                                "fallback_reason": None, "source_provenance": "consistent",
                                "footprints": {stage: {"status": "unavailable", "functions": {}, "totals": None}
                                               for stage in ("before", "after")}}}
            self.report["attempts"].append(self.attempt)
            self.diagnostics.PHASE = "semantic"
            try:
                result = original(gen, *args, **kwargs)
            except Rejoin as retry:
                reason = ("dynamic slice iterator acquisition requires exception handling" if isinstance(retry, NeedSliceEH)
                          else "compiler requested a fresh semantic attempt")
                self.attempt.update(status="retry", reason=reason,
                                    new_type_hints=len(gen.newhints), declined_methods=len(gen.newx),
                                    identity_retry=bool(gen.idevent))
                raise
            else:
                self.attempt["status"] = "completed"
                return result
            finally:
                boundary = self.attempt["dynamic_boundary"]
                boundary["fallback_reason"] = gen.idevent or None
                for footprint in boundary["footprints"].values():
                    if footprint["status"] != "unavailable":
                        footprint["totals"] = self.boundary_totals(footprint["functions"])
                        if self.attempt["status"] == "completed":
                            footprint["status"] = "completed"
                # specdone contains only completed requests. A fresh Gen owns
                # each retry, so copy its aliases and fields before it is lost.
                selected = {}
                for key, identity in gen.specdone.items():
                    if identity not in selected:
                        cls = gen.classes[identity]
                        selected[identity] = {
                            "template": cls.origin, "bindings": dict(cls.tvars),
                            "fields": {name: cls.ftypes[name] for name in cls.fields},
                            "request_keys": [],
                        }
                    selected[identity]["request_keys"].append(key)
                self.attempt["class_specializations"] = selected
        return wrapped

    def effects_wrapper(self, original):
        def wrapped(gen, *args, **kwargs):
            result = original(gen, *args, **kwargs)
            self.capture_before(gen)
            return result
        return wrapped

    def verify_wrapper(self, original):
        def wrapped(gen, *args, **kwargs):
            old = self.diagnostics.PHASE
            self.diagnostics.PHASE = "verify"
            result = original(gen, *args, **kwargs)
            self.report["verification"]["calls"] += 1
            self.diagnostics.PHASE = old
            return result
        return wrapped

    def pass_wrapper(self, name: str):
        def decorate(original):
            def wrapped(gen, fn, *args, **kwargs):
                old = self.diagnostics.PHASE
                self.diagnostics.PHASE = "exceptions" if name == "exceptions" else "optimize"
                before = self.snapshot(fn) if self.selected(fn) and (not self.typed_after_only or (self.guard_evidence and name == "nullcheck")) else None
                result = original(gen, fn, *args, **kwargs)
                if before is not None:
                    after = self.snapshot(fn)
                    if self.guard_evidence and name == "nullcheck":
                        self.nullcheck_evidence.append({"before": before, "after": after,
                                                        "reported_rewrites": result})
                if before is not None and not self.typed_after_only:
                    # (typed-after-only records no pass records or diffs: only guard evidence)
                    # Function metadata is not itself a typed operation rewrite.
                    previous, current = self.render(before), self.render(after)
                    changed = previous != current
                    diff_path = None
                    if changed:
                        diff_path = f"passes/{len(self.report['passes']) + 1:04d}-{name}.diff"
                        (self.output / "passes").mkdir(exist_ok=True)
                        (self.output / diff_path).write_text("".join(difflib.unified_diff(
                            previous, current, fromfile=f"{fn.f.ll}:before-{name}",
                            tofile=f"{fn.f.ll}:after-{name}")), encoding="utf-8")
                    self.report["passes"].append({
                        "attempt": self.attempt["index"] if self.attempt else 0,
                        "name": name, "function": fn.f.ll,
                        "reported_rewrites": result if isinstance(result, int) else None,
                        "changed": changed, "before_operations": self.counts(before),
                        "after_operations": self.counts(after), "diff": diff_path,
                        "rule": PASS_RULES[name], "explanation_scope": "general pass contract",
                    })
                self.diagnostics.PHASE = old
                return result
            return wrapped
        return decorate

    @staticmethod
    def program_totals(functions: dict) -> dict:
        operations = Counter()
        for fn in functions.values():
            operations.update(fn["operations"])
        return {"functions": len(functions), "slots": sum(fn["slots"] for fn in functions.values()),
                "operation_count": sum(operations.values()), "operations": dict(sorted(operations.items())),
                "guards": {name: operations["rt:recursion." + name] for name in RECURSION_OPS}}

    def program_snapshot(self, gen) -> dict:
        functions, selected = {}, {}
        for fn in gen.fns:
            snapshot = self.snapshot(fn)
            operations = self.counts(snapshot)
            functions[fn.f.ll] = {
                "snapshot_sha256": hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
                "operations": operations, "slots": len(snapshot["slots"]),
                "guards": {name: operations.get("rt:recursion." + name, 0) for name in RECURSION_OPS},
                "recursion": dict(snapshot["recursion"], closed=fn.f.ll in gen.rdpass),
            }
            if self.selected(fn):
                selected[fn.f.ll] = snapshot
        return {"function_order": [fn.f.ll for fn in gen.fns], "functions": functions,
                "selected_snapshots": selected, "totals": self.program_totals(functions),
                "selected_totals": self.program_totals({key: functions[key] for key in selected})}

    def program_pass_wrapper(self, name: str):
        def decorate(original):
            def wrapped(gen, *args, **kwargs):
                old = self.diagnostics.PHASE
                self.diagnostics.PHASE = "optimize"
                if self.typed_after_only:
                    result = original(gen, *args, **kwargs)
                    self.diagnostics.PHASE = old
                    return result
                before = self.program_snapshot(gen)
                result = original(gen, *args, **kwargs)
                after = self.program_snapshot(gen)
                previous, current = before["functions"], after["functions"]
                added = [key for key in current if key not in previous]
                removed = [key for key in previous if key not in current]
                changed = [key for key in current if key in previous and current[key] != previous[key]]
                stem = f"program-passes/{len(self.report['program_passes']) + 1:04d}-{name}"
                (self.output / "program-passes").mkdir(exist_ok=True)
                write_json(self.output / (stem + ".json"), {"before": before, "after": after})
                selected_before, selected_after = before["selected_snapshots"], after["selected_snapshots"]
                diff = []
                for key in sorted(selected_before.keys() | selected_after.keys()):
                    left = self.render(selected_before[key]) if key in selected_before else []
                    right = self.render(selected_after[key]) if key in selected_after else []
                    diff.extend(difflib.unified_diff(left, right, fromfile=f"{key}:before-{name}",
                                                   tofile=f"{key}:after-{name}"))
                if diff:
                    (self.output / (stem + ".diff")).write_text("".join(diff), encoding="utf-8")
                order_changed = before["function_order"] != after["function_order"]
                self.report["program_passes"].append({
                    "attempt": self.attempt["index"] if self.attempt else 0, "name": name,
                    "scope": "whole program", "reported_transformations": result if type(result) is int else None,
                    "return_unit": PROGRAM_PASS_UNITS[name],
                    "changed": bool(added or removed or changed or order_changed),
                    "added_functions": added, "removed_functions": removed, "changed_functions": changed,
                    "order_changed": order_changed, "snapshot": stem + ".json",
                    "diff": stem + ".diff" if diff else None,
                    "before_totals": before["totals"], "after_totals": after["totals"],
                    "before_selected_totals": before["selected_totals"], "after_selected_totals": after["selected_totals"],
                    "rule": PASS_RULES[name], "explanation_scope": "general pass contract; zero does not identify a refusal reason",
                })
                self.diagnostics.PHASE = old
                return result
            return wrapped
        return decorate

    def split_record(self, fn) -> list:
        """The split union slot pairs of fn that unionslots made and fn still holds."""
        kept, entries = self.split_unions.get(id(fn), (None, []))
        if kept is not fn:
            return []
        present = {f"%{s.s or 'h'}.{s.r[0]}" for s in fn.slots if len(s.r) == 1 and s.k == 0}
        return [entry for entry in entries if entry["tag"] in present and entry["payload"] in present]

    def unionslots_wrapper(self, original):
        def wrapped(gen, fn, *args, **kwargs):
            # optimizations.gen_unionslots replaces each slot it splits, in slot order, by a tag
            # slot and a payload slot it appends in that order: pair them by that order and name
            before = [(s.s, s.r[0], s.t) for s in fn.slots if s.k == 0 and len(s.r) == 1]
            known = {id(s) for s in fn.slots}
            result = original(gen, fn, *args, **kwargs)
            remaining = {(s.s, s.r[0]) for s in fn.slots if s.k == 0 and len(s.r) == 1}  # (a flag keeps its number)
            removed = [entry for entry in before if (entry[0], entry[1]) not in remaining]
            created = [s for s in fn.slots if id(s) not in known]
            entries = []
            if len(created) == 2 * len(removed):
                for index, (name, _, typ) in enumerate(removed):
                    tag, payload = created[2 * index], created[2 * index + 1]
                    base = name or "h"
                    if (tag.s, payload.s) != (base + ".tag", base + ".pay") or tag.t != "int" or payload.t != "int":
                        entries = []
                        break
                    entries.append({"tag": f"%{tag.s}.{tag.r[0]}", "payload": f"%{payload.s}.{payload.r[0]}",
                                    "type": typ})
            # (a record that does not pair up is left out: the adapter then refuses those slots)
            if entries:
                kept, recorded = self.split_unions.get(id(fn), (fn, []))
                self.split_unions[id(fn)] = (fn, (recorded if kept is fn else []) + entries)
            return result
        return wrapped

    def lower_wrapper(self, original):
        def wrapped(gen, fn, *args, **kwargs):
            self.capture_before(gen)
            if self.attempt is not None:
                footprint = self.attempt["dynamic_boundary"]["footprints"]["after"]
                footprint["status"] = "partial"
                footprint["functions"][fn.f.ll] = self.boundary_function(gen, fn)
            if self.selected(fn):
                self.after.append(self.snapshot(fn))
            self.diagnostics.PHASE = "lower"
            return original(gen, fn, *args, **kwargs)
        return wrapped

    def install(self) -> None:
        from src.pystachy_compiler import optimizations
        from src.pystachy_compiler.gen import Gen
        from src.pystachy_compiler.lexer import Lexer
        from src.pystachy_compiler.loader import Loader
        from src.pystachy_compiler.optimizations import PASS_CONTRACTS
        from src.pystachy_compiler.parser import Parser
        self.wrap(Loader, "program", self.phase_wrapper("load"))
        self.wrap(Loader, "parse_source", self.parse_wrapper)
        self.wrap(Lexer, "file", self.phase_wrapper("lex"))
        self.wrap(Parser, "module", self.phase_wrapper("parse"))
        self.wrap(Gen, "program", self.program_wrapper)
        self.wrap(Gen, "identity_modules", self.identity_wrapper)
        for name in ("held_value", "held_read", "held_pair"):
            self.wrap(Gen, name, self.held_representation_wrapper(name))
        self.wrap(Gen, "big_popitem", self.big_popitem_wrapper)
        self.wrap(Gen, "search_hold", self.search_hold_wrapper)
        self.wrap(optimizations, "clone_instruction", self.clone_instruction_wrapper)
        self.wrap(Gen, "effects", self.effects_wrapper)
        self.wrap(Gen, "verify", self.verify_wrapper)
        for contract in PASS_CONTRACTS:
            self.report["pass_contracts"][contract.name] = {
                key: list(getattr(contract, key))
                for key in ("requires", "analyses", "preserves", "invalidates", "rerun")
            }
            self.wrap(Gen, contract.name, self.pass_wrapper(contract.name))
        if self.guard_evidence:
            self.wrap(Gen, "unionslots", self.unionslots_wrapper)
        for name in PROGRAM_PASS_UNITS:
            self.wrap(Gen, name, self.program_pass_wrapper(name))
        self.wrap(Gen, "eh_ir", self.pass_wrapper("exceptions"))
        self.wrap(Gen, "lower", self.lower_wrapper)
        self.wrap(Gen, "lower_module", self.phase_wrapper("lower"))

    def restore(self) -> None:
        for cls, name, original in reversed(self.restores):
            setattr(cls, name, original)

    def save(self) -> None:
        if self.report["input"]["changed_during_compilation"]:
            for attempt in self.report["attempts"]:
                boundary = attempt["dynamic_boundary"]
                boundary["source_provenance"] = "inconsistent"
                for footprint in boundary["footprints"].values():
                    if footprint["status"] == "completed":
                        footprint["status"] = "partial"
        # Partial snapshots remain explicitly partial, never a completed pipeline.
        for name, functions, available in (("typed-before", self.before, self.captured_before and not self.typed_after_only),
                                           ("typed-after", self.after, bool(self.after) or self.report["status"] == "ok")):
            if available:
                artifact = name + ".json"
                state = "completed" if self.report["status"] == "ok" else "partial"
                snapshot = {"schema_version": SCHEMA_VERSION, "stage": name, "status": state,
                            "attempt": self.attempt["index"] if self.attempt else 0, "functions": functions}
                if name == "typed-after" and self.gen is not None:
                    snapshot["dynamic_types"] = self.dynamic_types(self.gen)
                    snapshot["classes"] = self.classes(self.gen)
                    if self.guard_evidence:
                        snapshot["class_layouts"] = self.class_layouts(self.gen)
                        snapshot["union_tags"] = dict(self.gen.utags)
                        # (each type hole's resolved type, which lowering reads to allocate an empty
                        # list or dict a later use typed: check_lean_gc.py)
                        snapshot["holes"] = list(self.gen.holes)
                        # (the text of each string constant whose address a dict or set's key kind
                        # is, a hash descriptor: runtime.c's keymem reads its first character)
                        snapshot["key_descriptors"] = self.key_descriptors(self.gen, functions)
                        snapshot["nullcheck_evidence"] = self.nullcheck_evidence
                        snapshot["guard_inventory"] = {"nullcheck_passes": len(self.nullcheck_evidence),
                            "removed_checks": sum(r["reported_rewrites"] for r in self.nullcheck_evidence)}
                write_json(self.output / artifact, snapshot)
                self.report["artifacts"][name] = artifact
                for stage in self.report["stages"]:
                    if stage["name"] == name:
                        stage.update(status=state, artifact=artifact)


def worker(args) -> int:
    sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import diagnostics, driver
    output = Path(args.output)
    typed_after_only = getattr(args, "typed_after_only", False)
    report = base_report(args.source, args.function, typed_after_only)
    if typed_after_only:
        report["stages"][0]["status"] = "skipped"
    observer = Observer(report, output, args.function, typed_after_only, getattr(args, "guard_evidence", False))
    diagnostics.CAPTURE = True
    diagnostics.CAPTURED.clear()
    diagnostics.PHASE = "input"
    observer.install()
    start = time.monotonic()
    old_argv = sys.argv
    exitcode = 2
    try:
        sys.argv = [str(ROOT / "pystachy.py"), "ir", args.source, "-o", str(output / "llvm.ll")]
        with (output / "compiler.stderr").open("w", encoding="utf-8") as stderr, \
             (output / "compiler.stdout").open("w", encoding="utf-8") as stdout, \
             redirect_stderr(stderr), redirect_stdout(stdout):
            try:
                source_path = Path(args.source)
                if source_path.exists() and not source_path.is_file():
                    raise OSError("inspection input must be a regular file")
                driver.main()
            except SystemExit as error:
                code = error.code if isinstance(error.code, int) else 1
                report["status"] = ("rejected" if code == 1 and diagnostics.CAPTURED
                                    and diagnostics.PHASE != "input" else "error")
                exitcode = 1 if report["status"] == "rejected" else 2
            except Exception as error:
                report["diagnostics"].append(tool_diagnostic("PYS9001", diagnostics.PHASE,
                    f"{type(error).__name__}: {error}", args.source))
                traceback.print_exc()
            else:
                report["status"] = "ok"
                report["verification"]["completed"] = True
                report["artifacts"]["llvm"] = "llvm.ll"
                report["stages"][-1].update(status="completed", artifact="llvm.ll")
                exitcode = 0
    finally:
        sys.argv = old_argv
        observer.restore()
    for error in diagnostics.CAPTURED:
        report["diagnostics"].append({key: getattr(error, key) for key in
            ("code", "severity", "phase", "message", "file", "line", "context") } | {"column": None})
    if any(d["code"] == "PYS9000" for d in report["diagnostics"]):
        report["status"], exitcode = "error", 2
    for source_read in observer.source_reads:
        source_read["changed_since_read"] |= digest(Path(source_read["path"])) != source_read["sha256"]
    report["input"]["modules"] = observer.source_reads
    for source_read in observer.source_reads:
        if source_read["path"] == args.source:
            report["input"]["sha256"] = source_read["sha256"]
            report["input"]["source_sha256"] = source_read["source_sha256"]
            break
    if any(source_read["changed_since_read"] for source_read in observer.source_reads):
        report["input"]["changed_during_compilation"] = True
        report["status"], exitcode = "error", 2
        report["verification"]["completed"] = False
        report["diagnostics"].append(tool_diagnostic("PYS9003", "provenance",
            "Source files changed during compilation; snapshots describe the consumed source hashes, not the current files",
            args.source))
        for stage in report["stages"]:
            if stage["status"] == "completed":
                stage["status"] = "partial"
    report["elapsed_seconds"] = time.monotonic() - start
    report["artifacts"].update(stderr="compiler.stderr", stdout="compiler.stdout")
    observer.save()
    write_json(output / "report.json", report)
    return exitcode


def positive_timeout(value: str) -> float:
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return seconds


def run_worker(args, output: Path) -> int:
    """Run in staging; do not introduce an importable requested output directory."""
    env = os.environ.copy()
    env["PYSTACHY_IRCHECK"] = "1"
    typed_after_only = getattr(args, "typed_after_only", False)
    command = [sys.executable, str(Path(__file__).resolve()), args.source, "--output", str(output),
               "--function", args.function, "--_worker"] + (["--typed-after-only"] if typed_after_only else []) + (["--guard-evidence"] if getattr(args, "guard_evidence", False) else [])
    start = time.monotonic()
    try:
        with (output / "worker.stderr").open("w", encoding="utf-8") as errors:
            run = subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=errors, timeout=args.timeout)
        exitcode = run.returncode
    except (subprocess.TimeoutExpired, OSError) as error:
        report = base_report(args.source, args.function, typed_after_only)
        timeout = isinstance(error, subprocess.TimeoutExpired)
        report["status"] = "timeout" if timeout else "error"
        report["diagnostics"].append(tool_diagnostic("PYS9002" if timeout else "PYS9001", "worker",
            f"Compilation worker exceeded {args.timeout:g} seconds" if timeout else str(error), args.source))
        report["elapsed_seconds"] = time.monotonic() - start
        write_json(output / "report.json", report)
        exitcode = 124 if timeout else 2
    if not (output / "report.json").exists():
        report = base_report(args.source, args.function, typed_after_only)
        report["diagnostics"].append(tool_diagnostic("PYS9001", "worker",
            f"Compilation worker exited {exitcode} without a report; see worker.stderr", args.source))
        report["elapsed_seconds"] = time.monotonic() - start
        write_json(output / "report.json", report)
        exitcode = 2
    return exitcode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="program to compile without running it")
    parser.add_argument("--output", required=True, help="new directory for report and snapshots (must not exist)")
    parser.add_argument("--function", default="", help="filter snapshot functions by symbol/name substring; compilation is still complete")
    parser.add_argument("--timeout", type=positive_timeout, default=120.0, help="worker deadline in seconds (default: 120)")
    parser.add_argument("--typed-after-only", action="store_true",
                        help="record only the typed-after snapshot: no typed-before snapshot, pass records or diffs")
    parser.add_argument("--guard-evidence", action="store_true",
                        help="retain union tags and nullcheck pass inputs/outputs for independent checking")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    args.source = str(Path(args.source).absolute())
    args.output = str(Path(args.output).absolute())
    if args._worker:
        return worker(args)
    output = Path(args.output)
    if output.exists() or output.is_symlink():
        print(f"inspect_compiler: output directory must not exist: {output}", file=sys.stderr)
        return 2
    try:
        # A dot/hyphen name cannot become a Python import component, even when
        # the user's source lives in the system temporary directory itself.
        with tempfile.TemporaryDirectory(prefix=".pystachy-inspect-") as temporary:
            staged = Path(temporary)
            exitcode = run_worker(args, staged)
            # Reserve only after compilation, and never replace an existing path.
            output.mkdir(parents=True, exist_ok=False)
            shutil.copytree(staged, output, dirs_exist_ok=True)
    except OSError as error:
        print(f"inspect_compiler: cannot publish inspection output: {error}", file=sys.stderr)
        return 2
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    changed = sum(bool(p["changed"]) for p in report["passes"])
    program_changed = sum(bool(p["changed"]) for p in report["program_passes"])
    print(f"{report['status']}: {output / 'report.json'} ({changed} changed function-pass records, {program_changed} changed program-pass records)")
    return exitcode


if __name__ == "__main__":
    raise SystemExit(main())
