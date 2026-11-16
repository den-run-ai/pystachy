"""Reports of ``pystachy check``: diagnostics by unit and the checked program's decisions.

The decisions of a completed attempt are kept apart as the compiler made them: the types
each compiled unit was checked with, the layouts chosen for classes, and the specializations
that templates were compiled into. They describe what the compiler decided for the code it
reached, not a PEP 484 type check of the source.
"""
from __future__ import annotations
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.checking import check_kind, check_name
from src.pystachy_compiler.diagnostics import DYNFILES, FILES, INTFILES, LINES, CheckFailed, shown, where
from src.pystachy_compiler.gen import Gen
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.specs import SPECSHOW
from src.pystachy_compiler.utils import lib_file, lt, typestr


class CheckRun:
    # One pystachy check: the bodies left out so far (Gen.fnkey), the failures in the order the
    # attempts met them, and the Gen of the attempt that completed finalization, if one did
    def __init__(self):
        self.stubs: dict[str, bool] = {}
        self.failures: list[CheckFailed] = []
        self.attempts = 0
        self.done = False
        self.stopped = ""
        self.gen: Gen | None = None


def check_errors(run: CheckRun) -> int:
    # the failures that are errors of their own: not consequences of a unit left out
    return len([e for e in run.failures if e.after == ""])


def check_text(run: CheckRun) -> list[str]:
    # the human report, one diagnostic per line, as compilation writes them; units that fail
    # with the same message at the same line (an inherited method, for each receiver class)
    # share one line, and the JSON report lists each
    out: list[str] = []
    for e in run.failures:
        d = e.diag
        if e.after == "":
            line = f"{d.file}:{d.line}: error: {d.message}"
            if line not in out:
                out.append(line)
        elif e.name != "":
            out.append(f"{e.place}: note: {e.name} was not checked: its types may depend on {e.after}, which failed")
        else:
            out.append(f"{d.file}:{d.line}: note: not checked: this code's types may depend on {e.after}, which failed")
    if run.stopped != "":
        out.append(f"{diagnostics.SRC}: note: {run.stopped}")
    return out


def jstr(s: str) -> str:
    # s as a JSON string: the compiler's str holds the source's bytes, which are written as they
    # are (UTF-8 source stays UTF-8); quotes, backslashes and control characters are escaped
    out: list[str] = ['"']
    for c in s:
        if c == '"' or c == "\\":
            out.append("\\" + c)
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 32 or ord(c) == 127:
            out.append("\\u00" + "0123456789abcdef"[ord(c) // 16] + "0123456789abcdef"[ord(c) % 16])
        else:
            out.append(c)
    out.append('"')
    return "".join(out)


def jlist(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def jobj(fields: list[str]) -> str:
    # fields: '"name": value' members, in order
    return "{" + ", ".join(fields) + "}"


def check_status(run: CheckRun) -> str:
    if len(run.failures) == 0:
        return "ok"
    return "incomplete" if run.stopped != "" else "errors"


def failure_json(e: CheckFailed) -> str:
    d = e.diag
    unit = jobj([f'"name": {jstr(e.name)}', f'"kind": {jstr(e.kind)}', f'"place": {jstr(e.place)}'])
    return jobj([f'"severity": {jstr("error" if e.after == "" else "note")}', f'"code": {jstr(d.code)}',
                 f'"file": {jstr(d.file)}', f'"line": {d.line}', f'"message": {jstr(d.message)}',
                 f'"context": {jlist([jstr(x) for x in d.context])}', f'"unit": {unit}',
                 f'"after": {jstr(e.after)}', f'"body_left_out": {"true" if e.key != "" and e.body else "false"}'])


def check_json(run: CheckRun) -> str:
    # the JSON report: the outcome, each failure and, when an attempt completed, the decisions it
    # made for the program's own files (not lib/'s), kept apart: the types each compiled unit was
    # checked with, the class layouts, the template specializations, the files' representation
    # policies, and the units no compiled code reached
    fields = ['"version": 1', f'"file": {jstr(diagnostics.SRC)}', f'"status": {jstr(check_status(run))}',
              f'"attempts": {run.attempts}', f'"errors": {check_errors(run)}',
              f'"stopped": {jstr(run.stopped)}',
              f'"diagnostics": {jlist([failure_json(e) for e in run.failures])}']
    g = run.gen
    if run.done and g is not None:
        fields.append(f'"typing": {jlist(typing_json(g))}')
        fields.append(f'"layouts": {jlist(layouts_json(g))}')
        fields.append(f'"specializations": {jlist(specializations_json(g))}')
        fields.append(f'"policies": {jlist(policies_json(g))}')
        fields.append(f'"unreached": {jlist(unreached_json(g))}')
    return jobj(fields) + "\n"


def own(g: Gen, line: int) -> bool:
    # is the code at line in the program's own files (lib/'s modules are Pystachy's)
    return not lib_file(line, g.libdir)


def rep_shown(t: str) -> str:
    # a representation as the compiler names it, with module names as Python spells them
    # (heapq$X is heapq.X, the main program's own names unqualified) and layouts numbered (Box-1)
    s = t.replace("__main__$", "")
    out: list[str] = []
    for i in range(len(s)):
        c = s[i]
        if c == "$" and i > 0 and i + 1 < len(s) and (s[i - 1].isalnum() or s[i - 1] == "_") and (s[i + 1].isalnum() or s[i + 1] == "_"):
            c = "."
        out.append(c)
    return "".join(out)


def value_json(name: str, t: str) -> str:
    # a typed value three ways: the Python type it was checked as, the compiler's representation
    # of it (int+ is a promoting int, dyn a dynamic Any box, Box-1 a specialization's layout) and
    # the machine storage of that representation
    fields = [f'"type": {jstr(typestr(t))}', f'"representation": {jstr(rep_shown(t))}', f'"storage": {jstr(lt(t))}']
    return jobj(([f'"name": {jstr(name)}'] if name != "" else []) + fields)


def unit_status(g: Gen, f: FnInfo) -> str:
    if f.ll in g.stubbed:
        return "left out"
    return "partly checked" if f.ll in g.taint else "checked"


def typing_json(g: Gen) -> list[str]:
    # each body compiled from the program's files: the parameter and result types it was checked
    # with (one entry per template instance)
    out: list[str] = []
    for fn in g.fns:
        f = fn.f
        kind = check_kind(f)
        if kind == "" or not own(g, f.node.line):
            continue
        skip = 1 if f.clo >= 0 and len(f.ptypes) > 0 else 0  # (a closure's env)
        params = [value_json(f.params[i] if i < len(f.params) else "", f.ptypes[i]) for i in range(skip, len(f.ptypes))]
        fields = [f'"unit": {jstr("module code" if kind == "module" else check_name(f))}', f'"kind": {jstr(kind)}',
                  f'"place": {jstr(where(f.node.line))}', f'"symbol": {jstr(f.ll)}', f'"status": {jstr(unit_status(g, f))}',
                  f'"instance": {"true" if f.inst else "false"}', f'"parameters": {jlist(params)}']
        if kind != "module":
            fields.append(f'"result": {value_json("", f.ret)}')
            fields.append(f'"result_inferred": {"true" if f.infer else "false"}')
            fields.append(f'"returns": {"false" if f.noret else "true"}')
        out.append(jobj(fields))
    return out


def layouts_json(g: Gen) -> list[str]:
    # each class layout of the program's files: its members in struct order (fields, then the
    # hidden "is assigned" flags and identity boxes), and the class it is a layout of
    out: list[str] = []
    for name in g.classes:
        ci = g.classes[name]
        if not own(g, ci.node.line) or name in g.tmpl or not ci.fields_ready:
            continue
        fields = [value_json(shown(x), ci.ftypes[x]) for x in ci.fields if x in ci.ftypes]
        out.append(jobj([f'"class": {jstr(shown(ci.origin if ci.origin != "" else name))}',
                         f'"layout": {jstr(rep_shown(name))}', f'"shown": {jstr(SPECSHOW.get(name, shown(name)))}',
                         f'"place": {jstr(where(ci.node.line))}',
                         f'"specialization": {"true" if ci.origin != "" else "false"}',
                         f'"base": {jstr(shown(ci.base))}', f'"tagged": {"true" if ci.tag != 0 else "false"}',
                         f'"fields": {jlist(fields)}', f'"assignment_flags": {ci.nflag}', f'"identity_boxes": {ci.nbox}']))
    return out


def unit_defs(g: Gen) -> list[FnInfo]:
    # the declared functions and methods of the program's files, once each (a specialization's
    # methods are its template's), and their closures
    out: list[FnInfo] = []
    seen: dict[str, bool] = {}
    for f in g.funcs.values():
        if f.ll not in seen:
            seen[f.ll] = True
            out.append(f)
    for ci in g.classes.values():
        for f in ci.methods.values():
            if f.ll not in seen and f.cls == ci.name:
                seen[f.ll] = True
                out.append(f)
    for c in g.closures:
        if c.f.ll not in seen:
            seen[c.f.ll] = True
            out.append(c.f)
    return [f for f in out if own(g, f.node.line) and not f.synthetic and not f.extern]


def specializations_json(g: Gen) -> list[str]:
    # each template of the program's files the program compiled more than its declaration of:
    # a function's instances by the types of their arguments, a class's layouts by the types
    # of the call that made each
    out: list[str] = []
    for f in unit_defs(g):
        if len(f.insts) == 0:
            continue
        insts = [jobj([f'"instance": {jstr(check_name(f.insts[k]))}', f'"key": {jstr(g.stable(k))}',
                       f'"symbol": {jstr(f.insts[k].ll)}']) for k in f.insts]
        out.append(jobj([f'"template": {jstr(check_name(f).replace("()", ""))}', '"kind": "function"',
                         f'"place": {jstr(where(f.node.line))}', f'"instances": {jlist(insts)}']))
    for name in g.tmpl:
        if name not in g.classes or not own(g, g.classes[name].node.line):
            continue
        made = [x for x in g.classes.values() if x.origin == name]
        insts = [jobj([f'"instance": {jstr(SPECSHOW.get(x.name, shown(x.name)))}', f'"key": {jstr(g.stable(x.speckey))}',
                       f'"layout": {jstr(rep_shown(x.name))}']) for x in made]
        out.append(jobj([f'"template": {jstr(shown(name))}', '"kind": "class"',
                         f'"place": {jstr(where(g.classes[name].node.line))}', f'"instances": {jlist(insts)}']))
    return out


def policies_json(g: Gen) -> list[str]:
    # each file of the program's own: how it represents int (checked 64-bit, or promoting past 64
    # bits: # pystachy: python-int) and typing.Any (inferred concrete types, or dynamic boxes:
    # # pystachy: dynamic-any)
    out: list[str] = []
    for k in range(len(FILES)):
        if not own(g, k * LINES + 1):
            continue
        out.append(jobj([f'"file": {jstr(FILES[k])}', f'"int": {jstr("promoting" if k in INTFILES else "64-bit")}',
                         f'"any": {jstr("dynamic" if k in DYNFILES else "inferred")}']))
    return out


def unreached_json(g: Gen) -> list[str]:
    # the units of the program's files with no compiled body: no code the program compiles calls
    # them (templates are compiled per call), so nothing in them was checked; problem is what
    # compiling one would reject, where declaring it found that already
    compiled: dict[int, bool] = {}
    for fn in g.fns:
        compiled[fn.f.node.line] = True
    out: list[str] = []
    for f in unit_defs(g):
        if f.node.line in compiled or (f.cls != "" and f.name in g.abstracts.get(f.cls, [])):
            continue
        out.append(jobj([f'"unit": {jstr(check_name(f))}', f'"place": {jstr(where(f.node.line))}',
                         f'"template": {"true" if f.generic else "false"}', f'"problem": {jstr(shown(f.bad))}']))
    return out
