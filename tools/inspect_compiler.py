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
import subprocess
import sys
import tempfile
import time
import traceback


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
PASS_RULES = {
    "listget": "Replace a checked sequence-loop list read only when its index is in bounds and no intervening effect can shorten the list or run user code.",
    "dictfuse": "Reuse a known dictionary entry only while control flow, key equality and intervening effects preserve the lookup; mutation or user callbacks can invalidate it.",
    "unionslots": "Split eligible local union slots into tag/payload storage and reconstruct boxes at uses that require them.",
    "nullcheck": "Remove redundant null checks only where the existing control-flow proof establishes a non-null value.",
    "exceptions": "Lower retained exception regions using the compiler's conservative effect summaries.",
}
# Only compiler inputs are recorded, never arbitrary process environment values.
ENV_KEYS = (
    "PYSTACHY_HOME", "PYSTACHY_PATH", "PYSTACHY_OPT", "PYSTACHY_IRCHECK",
    "PYSTACHY_IRFX", "PYSTACHY_UNICODE_AUDIT",
)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


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


def base_report(source: str, function: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION, "status": "error",
        "compiler": compiler_identity(),
        "tool": {"path": "tools/inspect_compiler.py", "sha256": digest(Path(__file__))},
        "input": {"path": source, "sha256": digest(Path(source)), "modules": [],
                  "changed_during_compilation": False},
        "settings": {"environment": {k: os.environ[k] for k in ENV_KEYS if k in os.environ}
                     | {"PYSTACHY_IRCHECK": "1"},
                     "function_filter": function, "command": "ir", "executes_program": False,
                     "forced_environment": {"PYSTACHY_IRCHECK": "1"}},
        "diagnostics": [], "attempts": [], "passes": [],
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
        ],
    }


def tool_diagnostic(code: str, phase: str, message: str, source: str) -> dict:
    return {"code": code, "severity": "error", "phase": phase, "message": message,
            "file": source, "line": 0, "column": None, "context": []}


class Observer:
    """Read snapshots immediately: the compiler mutates ops and frees typed IR."""

    def __init__(self, report: dict, output: Path, function: str):
        from src.pystachy_compiler import diagnostics
        from src.pystachy_compiler.utils import fxs, typestr
        self.diagnostics = diagnostics
        self.fxs = fxs
        self.typestr = typestr
        self.report = report
        self.output = output
        self.function = function
        self.before: list[dict] = []
        self.after: list[dict] = []
        self.captured_before = False
        self.attempt: dict | None = None
        self.restores: list[tuple] = []
        self.source_reads: list[dict] = []

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
            "specialization": {"instantiated": f.inst, "generic": f.generic},
            "effects": self.fxs(fn.fx), "effects_scope": "last compiler analysis; may be conservative after rewrites",
            "slots": [self.instruction(i) for i in fn.slots],
            "blocks": [{"label": b.label, "handler": b.handler,
                        "operations": [self.instruction(i) for i in b.code]} for b in fn.blocks],
            "loops": [{"kind": lp.kind, "mode": lp.mode, "head": lp.head, "body": lp.body,
                       "step": lp.step, "exit": lp.exit, "tests": list(lp.tests), "indices": list(lp.idx)}
                      for lp in fn.loops],
        }

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
            self.before = [self.snapshot(fn) for fn in gen.fns if self.selected(fn)]
            self.captured_before = True
            if self.attempt is not None:
                self.attempt["typed_functions"] = len(gen.fns)
                self.attempt["selected_functions"] = len(self.before)
                self.attempt["enabled_optimizations"] = list(gen.opts)

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
        def wrapped(loader, source, line):
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
            result = original(loader, source, line)
            self.diagnostics.PHASE = old
            return result
        return wrapped

    def program_wrapper(self, original):
        def wrapped(gen, *args, **kwargs):
            from src.pystachy_compiler.diagnostics import Rejoin
            self.before, self.after = [], []
            self.captured_before = False
            self.attempt = {"index": len(self.report["attempts"]) + 1, "status": "failed"}
            self.report["attempts"].append(self.attempt)
            self.diagnostics.PHASE = "semantic"
            try:
                result = original(gen, *args, **kwargs)
            except Rejoin:
                self.attempt.update(status="retry", reason="compiler requested a fresh semantic attempt",
                                    new_type_hints=len(gen.newhints), declined_methods=len(gen.newx),
                                    identity_retry=bool(gen.idevent))
                raise
            else:
                self.attempt["status"] = "completed"
                return result
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
                before = self.snapshot(fn) if self.selected(fn) else None
                result = original(gen, fn, *args, **kwargs)
                if before is not None:
                    after = self.snapshot(fn)
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

    def lower_wrapper(self, original):
        def wrapped(gen, fn, *args, **kwargs):
            self.capture_before(gen)
            if self.selected(fn):
                self.after.append(self.snapshot(fn))
            self.diagnostics.PHASE = "lower"
            return original(gen, fn, *args, **kwargs)
        return wrapped

    def install(self) -> None:
        from src.pystachy_compiler.gen import Gen
        from src.pystachy_compiler.lexer import Lexer
        from src.pystachy_compiler.loader import Loader
        from src.pystachy_compiler.parser import Parser
        self.wrap(Loader, "program", self.phase_wrapper("load"))
        self.wrap(Loader, "parse_source", self.parse_wrapper)
        self.wrap(Lexer, "file", self.phase_wrapper("lex"))
        self.wrap(Parser, "module", self.phase_wrapper("parse"))
        self.wrap(Gen, "program", self.program_wrapper)
        self.wrap(Gen, "effects", self.effects_wrapper)
        self.wrap(Gen, "verify", self.verify_wrapper)
        for name in ("listget", "dictfuse", "unionslots", "nullcheck"):
            self.wrap(Gen, name, self.pass_wrapper(name))
        self.wrap(Gen, "eh_ir", self.pass_wrapper("exceptions"))
        self.wrap(Gen, "lower", self.lower_wrapper)
        self.wrap(Gen, "lower_module", self.phase_wrapper("lower"))

    def restore(self) -> None:
        for cls, name, original in reversed(self.restores):
            setattr(cls, name, original)

    def save(self) -> None:
        # Partial snapshots remain explicitly partial, never a completed pipeline.
        for name, functions, available in (("typed-before", self.before, self.captured_before),
                                           ("typed-after", self.after, bool(self.after) or self.report["status"] == "ok")):
            if available:
                artifact = name + ".json"
                state = "completed" if self.report["status"] == "ok" else "partial"
                write_json(self.output / artifact, {"schema_version": SCHEMA_VERSION, "stage": name,
                           "status": state, "attempt": self.attempt["index"] if self.attempt else 0,
                           "functions": functions})
                self.report["artifacts"][name] = artifact
                for stage in self.report["stages"]:
                    if stage["name"] == name:
                        stage.update(status=state, artifact=artifact)


def worker(args) -> int:
    sys.path.insert(0, str(ROOT))
    from src.pystachy_compiler import diagnostics, driver
    output = Path(args.output)
    report = base_report(args.source, args.function)
    observer = Observer(report, output, args.function)
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
    command = [sys.executable, str(Path(__file__).resolve()), args.source, "--output", str(output),
               "--function", args.function, "--_worker"]
    start = time.monotonic()
    try:
        with (output / "worker.stderr").open("w", encoding="utf-8") as errors:
            run = subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=errors, timeout=args.timeout)
        exitcode = run.returncode
    except (subprocess.TimeoutExpired, OSError) as error:
        report = base_report(args.source, args.function)
        timeout = isinstance(error, subprocess.TimeoutExpired)
        report["status"] = "timeout" if timeout else "error"
        report["diagnostics"].append(tool_diagnostic("PYS9002" if timeout else "PYS9001", "worker",
            f"Compilation worker exceeded {args.timeout:g} seconds" if timeout else str(error), args.source))
        report["elapsed_seconds"] = time.monotonic() - start
        write_json(output / "report.json", report)
        exitcode = 124 if timeout else 2
    if not (output / "report.json").exists():
        report = base_report(args.source, args.function)
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
    print(f"{report['status']}: {output / 'report.json'} ({changed} changed pass/function pairs)")
    return exitcode


if __name__ == "__main__":
    raise SystemExit(main())
