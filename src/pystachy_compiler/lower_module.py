"""LLVM module and native ABI lowering.

These serializers are the backend boundary for module data, native ABI adapters,
object dispatch and process/extension entry points. They do not create IR operations.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Data, FnInfo
from src.pystachy_compiler.llvm_abi import llstr
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import CTYPES, LINKDL, RTSYM, STRLEN_RANGE, TBAA_BYTES, TBAA_LEN
from src.pystachy_compiler.utils import RtFn, lt, runtime_decl, typestr


def gen_extern_decl(self, f: FnInfo) -> None:
    self.externs[f.ll] = f"declare {lt(f.ret)} {f.ll}({', '.join([lt(t) for t in f.ptypes])})"


def lower_data(d: Data) -> str:
    if d.kind == "string":
        n = len(d.text) + 1
        # Bytes are immutable; runtime.c's Str dictionary hash cache is writable.
        return f'{d.name} = private unnamed_addr global {{i64, i64, [{n} x i8]}} {{i64 {n - 1}, i64 0, [{n} x i8] c"{llstr(d.text)}\\00"}}, align 8'
    if d.kind == "callable" or d.kind == "exception":
        return f"{d.name} = private constant {{{', '.join(['ptr' for _ in d.refs])}}} {{{', '.join(['ptr ' + x for x in d.refs])}}}"
    fail(f"internal error: no LLVM lowering for module data {d.kind}", 0)
    return ""


def gen_cextern(self, f: FnInfo) -> None:
    # @ffi.extern: the program calls @f.<name> as any function, an internal stub that checks and
    # narrows C integers (OverflowError), passes a str as its bytes (const char *, NUL-terminated;
    # ValueError for a NUL in it) and copies a returned char * (NULL: None, or ValueError). It calls
    # the C function through @ffi.fp.<f.ll>, which the def statement set as ctypes.CDLL would find it, in
    # the library's own handle (pys_c_bind: see stmt's defaults)
    self.line = f.node.line
    sym = f.csym[1:]
    for pre in ("pys_", "pyx_", "PyInit_", "PyModExport_"):
        if sym.startswith(pre) or sym == "main":
            self.err(f"C function {sym} is reserved for Pystachy's runtime and extension modules")
    ps: list[str] = []
    args: list[str] = []
    code: list[str] = []
    cts: list[str] = []
    for j in range(len(f.ptypes)):
        t = f.ptypes[j]
        ps.append(f"{lt(t)} %a{j}")
        c = self.externtype(f.node.kids[0].kids[j].kids[0], t, "takes", f)
        if c == "str" or c == "c_buf":
            if c == "str":
                self.runtime("pys_c_str")
                code.append(f"  call void @pys_c_str(ptr %a{j})")
            code.append(f"  %p{j} = getelementptr i8, ptr %a{j}, i64 16")  # (the bytes, after the length and dict hash: runtime.c's Str)
            cts.append("ptr")
        elif c == "float":
            code.append(f"  %p{j} = bitcast double %a{j} to double")  # (as it is: -0.0, inf and nan too)
            cts.append("double")
        else:
            ll, k = CTYPES[c].split(":")
            v = f"%a{j}"
            if k != "-1":
                self.runtime("pys_c_check")
                code.append(f"  %k{j} = call i64 @pys_c_check(i64 %a{j}, i64 {k})")
                v = f"%k{j}"
            code.append(f"  %p{j} = {'trunc i64 ' + v + ' to i32' if ll.startswith('i32') else 'inttoptr i64 ' + v + ' to ptr' if ll == 'ptr' else 'add i64 0, ' + v}")
            cts.append(ll)
        args.append(f"{cts[-1]} %p{j}")
    c = self.externtype(f.node.kids[1], f.ret, "returns", f)
    r = "ptr" if c in ("str", "opt[str]") else "double" if c == "float" else "void" if c == "None" else CTYPES[c].split(":")[0]
    rr = r[r.find(" ") + 1 :] + " " + r[: r.find(" ")] if " " in r else r  # (a result's attribute comes first: zeroext i32)
    cl = f"call {rr} %fp({', '.join(args)})"
    code.insert(0, f"  %fp = load ptr, ptr @ffi.fp.{f.ll[1:]}")
    if r == "void":
        code.extend([f"  {cl}", "  ret void"])
    elif c == "str" or c == "opt[str]":
        self.runtime("pys_cstr")
        code.extend([f"  %r = {cl}", f"  %s = call ptr @pys_cstr(ptr %r, i64 {1 if c == 'str' else 0})", "  ret ptr %s"])
    elif c == "float":
        code.extend([f"  %r = {cl}", "  ret double %r"])
    else:
        k = CTYPES[c].split(":")[1]
        code.append(f"  %r = {cl}")
        code.append(f"  %x = {'sext i32 %r to i64' if r == 'i32 signext' else 'zext i32 %r to i64' if r == 'i32 zeroext' else 'ptrtoint ptr %r to i64' if r == 'ptr' else 'add i64 0, %r'}")
        if k == "2":
            self.runtime("pys_c_check")
            code.append("  %y = call i64 @pys_c_check(i64 %x, i64 3)")
        code.append(f"  ret i64 {'%y' if k == '2' else '%x'}")
    decl = f"declare {rr} {f.csym}({', '.join(cts)})"
    tys = [r.split(" ")[0]] + [x.split(" ")[0] for x in cts]
    if sym in RTSYM:
        # one the compiler or the runtime calls too (fabs, memchr, ...): RUNTIME's types
        e = RtFn(RTSYM[sym]).ll
        if tys != e:
            self.err(f"C function {sym} is declared as {tys[0]}({', '.join(tys[1:])}), but Pystachy's runtime calls it as {e[0]}({', '.join(e[1:])})")
    elif sym in self.csyms:
        if self.csyms[sym] != decl:
            self.err(f"C function {sym} is declared again with other types: {self.csyms[sym][8:]} at line {self.csymline[sym]}, {decl[8:]} here")
    else:
        self.csyms[sym] = decl
        self.csymline[sym] = f.node.line
    # (the C function's address, and the library and symbol pys_c_bind looks it up by)
    x = f.ll[1:]
    decl = f"@ffi.fp.{x} = internal global ptr null\n@ffi.lib.{x} = private unnamed_addr constant [{len(f.lib) + 1} x i8] c\"{llstr(f.lib)}\\00\"\n@ffi.sym.{x} = private unnamed_addr constant [{len(sym) + 1} x i8] c\"{llstr(sym)}\\00\""
    if len(LINKDL) == 0:
        LINKDL.append("dl")
    self.externs[f.ll] = decl + f"\ndefine internal {lt(f.ret)} {f.ll}({', '.join(ps)}) {{\n" + "\n".join(code) + "\n}"

def gen_pyext(self) -> list[str]:
    # pystachy ext: in place of @main, what pyext.c calls. @pyx.init runs the module's code and
    # each public function of the main module gets @pyx.f.<name>(ptr slots, ptr err): its
    # arguments in i64 slots, its result as one; a raise is caught there (none crosses CPython's
    # frames) and its Exc is stored in *err. pyx_exports lists them: name, signature (result,
    # then each parameter: i int, f float, b bool, s str, n None), wrapper
    o: list[str] = []
    for k in ["eh_on", "try_mark", "exc.handled", "exc.restore", "exc.begin", "personality", "init_lib"]:
        if k not in self.rtfns:
            o.append(runtime_decl(k))
    pad = ["lp:", "  %x = landingpad { ptr, i32 } catch ptr null", "  %ue = extractvalue { ptr, i32 } %x, 0",
           "  %e = call ptr @pys_exc_begin(ptr %ue, i64 %mark)", "  call void @pys_exc_restore(ptr %prev)"]
    o.extend(["declare void @pyx_argv()", "declare ptr @pyx_call(i64, ptr, i64, ptr)", "define ptr @pyx_init() personality ptr @pys_personality {",
              f"  call void @pys_init_lib(ptr @pys.roots, i64 {len(self.gcroots)})", "  call void @pyx_argv()", "  call void @pys_eh_on()", "  %mark = call i64 @pys_try_mark()", "  %prev = call ptr @pys_exc_handled()",
              "  invoke void @main.init() to label %ok unwind label %lp", "ok:", "  ret ptr null"] + pad + ["  ret ptr %e", "}"])
    tab: list[str] = []
    letter = {"int": "i", "float": "f", "bool": "b", "str": "s", "None": "n"}
    for f in self.funcs.values():
        if f.mod != "" or f.cls != "" or f.name.startswith("_") or f.extern:
            continue
        self.line = f.node.line
        if not f.pyexport:
            self.err(f"{f.name}() is public in extension module '{self.ext}' but not @export: CPython would not see it; export it or name it _{f.name}")
        dflt = False
        for x in f.defaults:
            dflt = dflt or x.kind != "noann"
        if dflt or f.vararg >= 0 or f.npos != len(f.params):
            self.err(f"{f.name}() is @export: its parameters are positional, with no default values and no *args (as CPython calls it)")
        for t in [f.ret] + f.ptypes:
            if t not in letter or (t == "None" and t != f.ret):
                self.err(f"{f.name}() cannot be called from CPython: it takes or returns {typestr(t) if t != '' else 'an untyped value'} (an extension module's function takes int, float, bool or str and returns one or None); name it _{f.name} to keep it private")
        sig = "".join([letter[t] for t in [f.ret] + f.ptypes])
        o.extend([f"define internal i64 @pyx.f.{f.name}(ptr %a, ptr %err) personality ptr @pys_personality {{", "entry:",
                  "  %mark = call i64 @pys_try_mark()", "  %prev = call ptr @pys_exc_handled()"])
        args: list[str] = []
        for j in range(len(f.ptypes)):
            t = lt(f.ptypes[j])
            o.extend([f"  %q{j} = getelementptr i64, ptr %a, i64 {j}", f"  %s{j} = load i64, ptr %q{j}"])
            o.append(f"  %v{j} = {'bitcast i64 %s' + str(j) + ' to double' if t == 'double' else 'trunc i64 %s' + str(j) + ' to i1' if t == 'i1' else 'inttoptr i64 %s' + str(j) + ' to ptr' if t == 'ptr' else 'add i64 0, %s' + str(j)}")
            args.append(f"{t} %v{j}")
        r = lt(f.ret)
        o.append(f"  {'%r = ' if r != 'void' else ''}invoke {r} {f.ll}({', '.join(args)}) to label %ok unwind label %lp")
        o.append("ok:")
        o.append(f"  %ri = {'bitcast double %r to i64' if r == 'double' else 'zext i1 %r to i64' if r == 'i1' else 'ptrtoint ptr %r to i64' if r == 'ptr' else 'add i64 0, %r' if r == 'i64' else 'add i64 0, 0'}")
        o.extend(["  ret i64 %ri"] + pad + ["  store ptr %e, ptr %err", "  ret i64 0", "}"])
        o.append(f"@pyx.n.{f.name} = private constant [{len(f.name) + 1} x i8] c\"{llstr(f.name)}\\00\"")
        o.append(f"@pyx.s.{f.name} = private constant [{len(sig) + 1} x i8] c\"{sig}\\00\"")
        # (its METH_FASTCALL | METH_KEYWORDS function: self is the module, the index says which)
        o.extend([f"define internal ptr @pyx.m.{f.name}(ptr %self, ptr %args, i64 %n, ptr %kw) {{",
                  f"  %r = call ptr @pyx_call(i64 {len(tab)}, ptr %args, i64 %n, ptr %kw)", "  ret ptr %r", "}"])
        tab.append(f"{{ptr, ptr, ptr, ptr}} {{ptr @pyx.n.{f.name}, ptr @pyx.s.{f.name}, ptr @pyx.f.{f.name}, ptr @pyx.m.{f.name}}}")
    o.append(f"@pyx_exports = constant [{len(tab) + 1} x {{ptr, ptr, ptr, ptr}}] [{', '.join(tab + ['{ptr, ptr, ptr, ptr} zeroinitializer'])}]")
    # what CPython would see of the module but an extension cannot give it yet: an error
    for ci in self.classes.values():
        if "$" not in ci.name and not ci.name.startswith("_"):
            self.line = ci.node.line
            self.err(f"class {ci.name} is public in extension module '{self.ext}', but classes cannot cross to CPython yet: name it _{ci.name}")
    for nm in self.mvars:
        if "$" not in nm and not nm.startswith("_") and nm not in self.imports and nm not in self.funcs and nm not in self.classes:
            self.line = self.extvars.get(nm, 1)
            self.err(f"variable '{nm}' is public in extension module '{self.ext}', but CPython would not see it (variables cannot cross yet): name it _{nm}")
    # a raise of one of the program's exception classes leaves as its nearest builtin base
    xs: list[str] = []
    for ci in self.classes.values():
        if ci.exc != "":
            o.append(f"@pyx.xn.{len(xs)} = private constant [{len(short(ci.name)) + 1} x i8] c\"{llstr(short(ci.name))}\\00\"")
            o.append(f"@pyx.xb.{len(xs)} = private constant [{len(ci.exc) + 1} x i8] c\"{ci.exc}\\00\"")
            xs.append(f"{{ptr, ptr}} {{ptr @pyx.xn.{len(xs)}, ptr @pyx.xb.{len(xs)}}}")
    o.append(f"@pyx_excbase = constant [{len(xs) + 1} x {{ptr, ptr}}] [{', '.join(xs + ['{ptr, ptr} zeroinitializer'])}]")
    o.append(f"@pyx.name = private constant [{len(self.ext) + 1} x i8] c\"{self.ext}\\00\"")
    # both entries: abi3's PyInit_<name> and abi3t's PyModExport_<name>; the driver keeps one
    o.extend(["declare ptr @pyx_module(ptr)", f"define ptr @PyInit_{self.ext}() {{", "  %m = call ptr @pyx_module(ptr @pyx.name)", "  ret ptr %m", "}"])
    o.extend(["declare ptr @pyx_slots(ptr)", f"define ptr @PyModExport_{self.ext}() {{", "  %m = call ptr @pyx_slots(ptr @pyx.name)", "  ret ptr %m", "}"])
    return o

def gen_dispatch(self, op: str) -> None:
    # pys_obj_<op>(class id, [op code,] a, b), called by the runtime for "O<id>" descriptors
    r = "ptr" if op == "repr" else "i64"
    self.out.append(f"define {r} @pys_obj_{op}(i64 %c, {'i64 %op, ' if op == 'cmp' else ''}i64 %a, i64 %b) {{")
    self.out.append("entry:")
    self.out.append("  %pa = inttoptr i64 %a to ptr")
    self.out.append("  %pb = inttoptr i64 %b to ptr")
    self.out.append(f"  switch i64 %c, label %none [{' '.join([f'i64 {self.ocls[c]}, label %k{self.ocls[c]}' for c in self.ocls])}]")
    for c in self.ocls:
        i = self.ocls[c]
        self.out.append(f"k{i}:")
        if op == "repr":
            self.out.append(f"  %r{i} = call ptr @o.repr.{c}(ptr %pa, ptr %pb)")
            self.out.append(f"  ret ptr %r{i}")
        else:
            self.out.append(f"  %r{i} = call i1 @o.{op}.{c}({'i64 %op, ' if op == 'cmp' else ''}ptr %pa, ptr %pb)")
            self.out.append(f"  %z{i} = zext i1 %r{i} to i64")
            self.out.append(f"  ret i64 %z{i}")
    self.out.append("none:")
    self.out.append("  unreachable")
    self.out.append("}")

def gen_lower_module(self) -> str:
    hdr: list[str] = ["; generated by pystachy"]
    for ci in self.classes.values():
        if ci.name in self.tmpl:
            continue  # (a class template's objects are its specializations')
        ts = [lt(ci.ftypes[x]) for x in ci.fields]
        for _ in range(ci.nflag):
            ts.append("i1")
        hdr.append(f"%C.{ci.name} = type {{{', '.join(ts)}}}")
    for g in self.globs:
        hdr.append(f"{g.v} = internal global {lt(g.t)} zeroinitializer")
    roots = ", ".join([f"ptr {g}" for g in self.gcroots])
    if not self.rtmode:
        hdr.append(f"@pys.roots = private constant [{len(self.gcroots)} x ptr] [{roots}]")
    for d in self.consts:
        hdr.append(lower_data(d))
    hdr.extend(self.out)
    for k in self.rtfns:
        if not (self.rtmode and self.rtfns[k].sym in self.rtdefs):
            hdr.append(runtime_decl(k))  # (runtime mode: what runtime.py defines is not declared)
    for x in self.externs.values():
        if x != "":
            hdr.append(x)
    if self.rtmode:
        for ci in self.classes.values():
            self.err(f"runtime.py may not define classes ({ci.name})")
        # TBAA: a str's length and its bytes never alias (see RTL); other accesses carry no tag
        hdr.append(f'!{TBAA_LEN - 3} = !{{!"pystachy runtime.py"}}')
        hdr.append(f'!{TBAA_LEN - 2} = !{{!"str length", !{TBAA_LEN - 3}, i64 0}}')
        hdr.append(f'!{TBAA_LEN - 1} = !{{!"str bytes", !{TBAA_LEN - 3}, i64 0}}')
        hdr.append(f"!{TBAA_LEN} = !{{!{TBAA_LEN - 2}, !{TBAA_LEN - 2}, i64 0}}")
        hdr.append(f"!{TBAA_BYTES} = !{{!{TBAA_LEN - 1}, !{TBAA_LEN - 1}, i64 0}}")
        hdr.append(f"!{STRLEN_RANGE} = !{{i64 0, i64 9223372036854775791}}")
        return "\n".join(hdr) + "\n"
    if self.ext != "":
        return "\n".join(hdr + self.pyext()) + "\n"
    # pys_init gets the GC roots: main's frame address bounds the stack scan (it also
    # covers @main.init if inlined here) and the table of pointer-typed globals
    hdr.append(runtime_decl("init"))
    hdr.append(runtime_decl("finish"))
    hdr.append(runtime_decl("frameaddress"))
    if self.eh:
        hdr.append(runtime_decl("eh_on"))
    hdr.append("define i32 @main(i32 %argc, ptr %argv) {")
    hdr.append("  %sb = call ptr @llvm.frameaddress.p0(i32 0)")
    hdr.append(f"  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr @pys.roots, i64 {len(self.gcroots)})")
    if self.eh:
        hdr.append("  call void @pys_eh_on()")  # (from now on, the runtime raises exceptions)
    hdr.append("  call void @main.init()")
    hdr.append("  call void @pys_finish()")
    hdr.append("  ret i32 0")
    hdr.append("}")
    return "\n".join(hdr) + "\n"
