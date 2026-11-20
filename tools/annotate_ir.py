#!/usr/bin/env python3
"""Annotate a program's source with the typed IR and the LLVM IR that each line compiles to.

As in Cython's annotate view, each Python line is followed by the typed-IR instructions that
carry its line, and each instruction by the LLVM lines that lowering emitted for it. A line's
heading counts its runtime calls (LLVM calls of `pys_` functions) and joins its instructions'
effects (docs/typed-ir.md#effects). The hosted compiler compiles the program once, in a worker
process, with line tables (PYSTACHY_DEBUG_LINES=1) and the IR check (PYSTACHY_IRCHECK=1); the
program is not run.

    python3 tools/annotate_ir.py PROGRAM.py                  # text, to stdout
    python3 tools/annotate_ir.py PROGRAM.py --html OUT.html  # a page for a browser
    python3 tools/annotate_ir.py PROGRAM.py --json OUT.json  # the records

The typed IR is what lowering prints: after the passes, and after machine_ir.py turns layout
reads such as list.len into machine loads. Effects are each instruction's as the analysis counts
them there, so a machine load through a raw pointer reads lists, dicts and objects alike. The
LLVM IR is what lowering emits, before LLVM optimizes it, without its !dbg tags. An instruction
with no line of its own is shown with the instruction before it, and a function's slots with its
def line. Only the program's own file is annotated: functions of the modules it imports are left
out.
"""
import argparse
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DBG = re.compile(r",? !dbg !pysdi\d+")
RUNTIME_CALL = re.compile(r"\b(?:call|invoke)\b[^@]*@pys_")
MODULE = "@main.init"


class AnnotateError(RuntimeError):
    """A program that did not compile, or a worker that failed."""


def capture(source):
    """The records of one compilation of source, in this process: run by the worker."""
    os.environ.update(PYSTACHY_DEBUG_LINES="1", PYSTACHY_IRCHECK="1")
    sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
    from src.pystachy_compiler import diagnostics, driver, utils
    from src.pystachy_compiler.gen import Gen
    from src.pystachy_compiler.source_lines import SourceLines
    import typed_ir_text

    def record(i):
        return {"op": i.op, "type": i.t, "text": i.s, "immediate": i.k, "descriptor": i.x, "results": list(i.r),
                "operands": [{"value": a.v, "type": a.t} for a in i.a], "targets": list(i.b), "line": i.line}

    functions = []
    state = {"fn": None, "ins": None, "blocks": {}}
    lower, lower_ins, mark = Gen.lower, Gen.lower_ins, SourceLines.mark

    def lowering(gen, fn):
        whole = typed_ir_text.from_ifn(fn)
        state["fn"] = {"symbol": fn.f.ll, "name": diagnostics.shown(fn.f.name), "line": fn.f.node.line,
                       "header": typed_ir_text.format_function(whole).split("\n", 1)[0],
                       "slots": [typed_ir_text.instruction_text(s) for s in whole["slots"]],
                       "prologue": [], "code": [], "define": ""}
        state["blocks"] = {id(i): b.label for b in fn.blocks for i in b.code}
        start = len(gen.out)
        lower(gen, fn)
        if len(gen.out) > start:
            state["fn"]["define"] = DBG.sub("", gen.out[-1].split("\n", 1)[0])
        functions.append(state["fn"])
        state["fn"] = None

    def lowering_ins(gen, fn, i):
        if id(i) not in state["blocks"]:
            # (lowering may rewrite a block's instructions before it lowers them)
            state["blocks"] = {id(x): b.label for b in fn.blocks for x in b.code}
        state["ins"] = {"block": state["blocks"].get(id(i), ""), "line": i.line, "op": i.op,
                        "typed": typed_ir_text.instruction_text(record(i)),
                        "effects": utils.fxs(gen.opfx(i, fn.fa)).split(), "llvm": []}
        state["fn"]["code"].append(state["ins"])
        lower_ins(gen, fn, i)

    def marking(lines, out, start, function, line):
        mark(lines, out, start, function, line)
        if state["fn"] is None:
            return
        emitted = [DBG.sub("", x).strip() for x in out[start:] if x.startswith("  ")]
        if state["ins"] is not None:
            state["ins"]["llvm"] = emitted
            state["ins"] = None
        elif not state["fn"]["code"]:
            state["fn"]["prologue"] = emitted

    Gen.lower, Gen.lower_ins, SourceLines.mark = lowering, lowering_ins, marking
    with tempfile.TemporaryDirectory(prefix="pystachy-annotate-") as directory:
        sys.argv = [str(ROOT / "pystachy.py"), "ir", str(source), "-o", str(Path(directory) / "program.ll")]
        try:
            driver.main()
        except SystemExit as stop:
            if stop.code not in (0, None):
                raise AnnotateError(f"{source} did not compile") from None
    own = [f for f in functions if 0 < f["line"] < diagnostics.LINES]
    return {"source": str(source), "text": Path(source).read_text(encoding="utf-8"), "functions": own,
            "lines": diagnostics.LINES}


def annotate(source, timeout=600):
    """The records of source, compiled by a worker process."""
    with tempfile.TemporaryDirectory(prefix="pystachy-annotate-") as directory:
        output = Path(directory) / "records.json"
        env = {key: value for key, value in os.environ.items() if not key.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        path = Path(source).resolve()
        if path.with_suffix(".path").is_file():
            env["PYSTACHY_PATH"] = path.with_suffix(".path").read_text().strip()
        done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_worker", str(path), str(output)],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        if done.returncode != 0 or not output.is_file():
            lines = [x for x in done.stderr.splitlines() if x.strip()] or ["the worker failed"]
            raise AnnotateError("; ".join(lines[-4:]))
        return json.loads(output.read_text(encoding="utf-8"))


def by_line(records):
    """Each source line's annotation, as (function, item) pairs in compilation order: a function's
    header and slots with its def line, block labels where they change, and instructions."""
    lines = {}
    limit = records["lines"]
    for fn in records["functions"]:
        last = fn["line"] if fn["symbol"] != MODULE else 0
        if fn["symbol"] != MODULE:
            lines.setdefault(last, []).append((fn, {"kind": "function"}))
        block = None
        for ins in fn["code"]:
            own = 0 < ins["line"] < limit
            if own:
                last = ins["line"]
            items = lines.setdefault(last, [])
            if ins["block"] != block or not items or items[-1][0] is not fn:
                items.append((fn, {"kind": "block", "label": ins["block"]}))
                block = ins["block"]
            items.append((fn, {"kind": "instruction", "ins": ins, "synthesized": not own}))
    return lines


def summary(items):
    """(the runtime calls, the joined effects) of one line's annotation."""
    calls = 0
    effects = []
    for fn, item in items:
        if item["kind"] == "instruction":
            calls += sum(1 for x in item["ins"]["llvm"] if RUNTIME_CALL.search(x))
            effects += [e for e in item["ins"]["effects"] if e not in effects and e != "N"]
        elif item["kind"] == "function":
            calls += sum(1 for x in fn["prologue"] if RUNTIME_CALL.search(x))
    return calls, effects


def render_text(records):
    """The annotation as text: each source line, then its typed IR, each with its LLVM below it."""
    lines = by_line(records)
    out = []
    source = records["text"].split("\n")
    if source and source[-1] == "":
        source.pop()
    width = len(str(len(source)))
    gutter = " " * width + " |"
    if 0 in lines:
        out.append(f"{'':>{width}} | (no source line)")
        out.extend(text_items(lines[0], gutter))
    for n, line in enumerate(source, 1):
        calls, effects = summary(lines.get(n, []))
        note = "; ".join(x for x in (f"{calls} runtime call{'s' if calls != 1 else ''}" if calls else "",
                                     " ".join(effects)) if x)
        out.append(f"{n:>{width}} | {line}" + (f"    ; {note}" if note else ""))
        out.extend(text_items(lines.get(n, []), gutter))
    return "\n".join(out) + "\n"


def text_items(items, gutter):
    out = []
    for fn, item in items:
        if item["kind"] == "function":
            out.append(f"{gutter}   {fn['header']}")
            out.extend(f"{gutter}       {x}" for x in [fn["define"]] if x)
            out.extend(f"{gutter}     {s}" for s in fn["slots"])
            out.extend(f"{gutter}         {x}" for x in fn["prologue"])
        elif item["kind"] == "block":
            out.append(f"{gutter}   {item['label'] or '(unnamed)'}:")
        else:
            ins = item["ins"]
            out.append(f"{gutter}     {ins['typed']}" + ("    ; line 0" if item["synthesized"] else ""))
            out.extend(f"{gutter}         {x}" for x in ins["llvm"])
    return out


STYLE = """
:root { --bg: #f6f7f6; --surface: #fff; --ink: #1b221e; --muted: #5b6761; --rule: #d8dfda; --accent: #4a7524;
  --heat1: rgba(234,179,8,.17); --heat2: rgba(234,179,8,.32); --heat3: rgba(234,179,8,.5); --rt: #855400; --raise: #a33a27; }
@media (prefers-color-scheme: dark) { :root { --bg: #121614; --surface: #181d1a; --ink: #e1e8e3; --muted: #9ba8a1;
  --rule: #2b342f; --accent: #9dcb6b; --heat1: rgba(250,204,21,.09); --heat2: rgba(250,204,21,.17);
  --heat3: rgba(250,204,21,.27); --rt: #efc15a; --raise: #f08b73; color-scheme: dark; } }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.5 system-ui, sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 24px max(16px, env(safe-area-inset-left, 0px)); }
h1 { font-size: 1.5rem; margin: 0 0 4px; } .lede { color: var(--muted); margin: 0 0 16px; max-width: 75ch; }
code, .src { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.listing { background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; font-size: .86rem; }
.ln, .ln > summary { display: grid; grid-template-columns: 3.4em minmax(0, 1fr) auto; gap: 10px; padding: 1px 12px; }
details.ln { display: block; padding: 0; } .ln > summary { cursor: pointer; list-style: none; }
.ln > summary::-webkit-details-marker { display: none; }
.heat1 > summary { background: var(--heat1); } .heat2 > summary { background: var(--heat2); }
.heat3 > summary { background: var(--heat3); }
.no { color: var(--muted); text-align: right; user-select: none; }
.src { white-space: pre; overflow-x: auto; } .meta { color: var(--rt); font-size: .75rem; white-space: nowrap; }
.ir { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); gap: 2px 18px; padding: 6px 14px 10px;
  border-block: 1px solid var(--rule); }
.ir > div { min-width: 0; } .ir code { display: block; white-space: pre; overflow-x: auto; font-size: .78rem; }
.label { color: var(--accent); font-weight: 600; } .syn { color: var(--muted); }
.raises { color: var(--raise); }
@media (max-width: 760px) { .ir { grid-template-columns: minmax(0, 1fr); } }
"""


def render_html(records):
    """The annotation as a self-contained page: each source line opens to its typed IR, beside
    the LLVM IR of each instruction, and is shaded by its runtime calls."""
    lines = by_line(records)
    source = records["text"].split("\n")
    if source and source[-1] == "":
        source.pop()
    rows = []
    for n, line in enumerate(source, 1):
        items = lines.get(n, [])
        code = html.escape(line) or "&nbsp;"
        if not items:
            rows.append(f'<div class="ln"><span class="no">{n}</span><span class="src">{code}</span></div>')
            continue
        calls, effects = summary(items)
        meta = " ".join(x for x in (f"{calls} runtime call{'s' if calls != 1 else ''}" if calls else "",
                                    " ".join(effects)) if x)
        rows.append(f'<details class="ln heat{min(calls, 3)}" open><summary><span class="no">{n}</span>'
                    f'<span class="src">{code}</span><span class="meta{" raises" if "R" in effects else ""}">'
                    f'{html.escape(meta)}</span></summary><div class="ir">')
        for fn, item in items:
            if item["kind"] == "function":
                typed = [fn["header"]] + ["  " + s for s in fn["slots"]]
                llvm = [fn["define"]] + fn["prologue"]
            elif item["kind"] == "block":
                label = html.escape(item["label"] or "(unnamed)") + ":"
                rows.append(f'<div><code class="label">{label}</code></div><div><code class="label">{label}</code></div>')
                continue
            else:
                typed = [item["ins"]["typed"] + ("    ; line 0" if item["synthesized"] else "")]
                llvm = item["ins"]["llvm"]
            rows.append("<div><code>" + "\n".join(html.escape(x) for x in typed) + "</code></div><div><code>"
                        + "\n".join(html.escape(x) for x in llvm if x) + "</code></div>")
        rows.append("</div></details>")
    title = html.escape(Path(records["source"]).name)
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}: annotated IR</title>'
            f"<style>{STYLE}</style></head><body><main><h1>{title}</h1>"
            '<p class="lede">Each line opens to the typed IR it compiles to, beside the LLVM IR that lowering emits '
            "for each instruction. The more runtime calls a line makes, the yellower it is.</p>"
            f'<div class="listing">{"".join(rows)}</div></main></body></html>\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path)
    parser.add_argument("--html", type=Path, help="write the annotation as a page")
    parser.add_argument("--json", type=Path, help="write the records")
    parser.add_argument("--timeout", type=float, default=600)
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["--_worker"]:
        try:
            records = capture(Path(argv[1]))
        except AnnotateError as error:
            print(f"annotate_ir: {error}", file=sys.stderr)
            return 1
        Path(argv[2]).write_text(json.dumps(records), encoding="utf-8")
        return 0
    args = parser.parse_args(argv)
    try:
        records = annotate(args.source, args.timeout)
    except (AnnotateError, OSError, subprocess.TimeoutExpired) as error:
        print(f"annotate_ir: {error}", file=sys.stderr)
        return 1
    if args.json:
        args.json.write_text(json.dumps(records, indent=1), encoding="utf-8")
    if args.html:
        args.html.write_text(render_html(records), encoding="utf-8")
    if not args.json and not args.html:
        sys.stdout.write(render_text(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
