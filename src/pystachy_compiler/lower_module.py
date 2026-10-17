"""LLVM module and native ABI lowering.

These serializers are the backend boundary for module data, native ABI adapters,
object dispatch and process/extension entry points. They do not create IR operations.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import Data, FnInfo
from src.pystachy_compiler.llvm_abi import llstr
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import CTYPES, GENCLEAN, GENCMD, GENDONE, GENNAME, GENRUN, GENSTATE, GLUE, LIBS, LINKDL, RANGEC, RTSYM, STRLEN_RANGE, TBAA_BYTES, TBAA_LEN
from src.pystachy_compiler.utils import RtFn, lt, runtime_decl, typestr


def gen_extern_decl(self, f: FnInfo) -> None:
    self.externs[f.ll] = f"declare {lt(f.ret)} {f.ll}({', '.join([lt(t) for t in f.ptypes])})"


def lower_data(d: Data) -> str:
    if d.kind == "string":
        n = len(d.text) + 1
        # Bytes are immutable; runtime.c's Str dictionary hash cache is writable.
        return f'{d.name} = private unnamed_addr global {{i64, i64, [{n} x i8]}} {{i64 {n - 1}, i64 0, [{n} x i8] c"{llstr(d.text)}\\00"}}, align 8'
    if d.kind == "tuple":
        # Fixed tuples use one i64 slot per item. These literals refer only to static strings,
        # so no heap allocation or collector root is needed; keep their address significant.
        slots = ["i64 ptrtoint (ptr " + v.v + " to i64)" if v.t == "str" else "i64 " + v.v for v in d.items]
        return f"{d.name} = private constant [{len(slots)} x i64] [{', '.join(slots)}], align 8"
    if d.kind == "callable" or d.kind == "exception":
        return f"{d.name} = private constant {{{', '.join(['ptr' for _ in d.refs])}}} {{{', '.join(['ptr ' + x for x in d.refs])}}}"
    if d.kind == "classrec":
        # a class's reflection record (reflection.py): name, qualified name and module, flags,
        # the sorted name table and the field table with their lengths (null and 0 until a site
        # needs them). Internal, and its address is the class's identity: never merged
        r = d.refs
        return (f"{d.name} = internal constant {{ptr, ptr, ptr, i64, i64, ptr, i64, ptr}} {{ptr {r[0]}, ptr {r[1]}, ptr {r[2]}, "
                f"i64 {d.items[0].v}, i64 {d.items[1].v}, ptr {r[3]}, i64 {d.items[2].v}, ptr {r[4]}}}, align 8")
    if d.kind == "classnames":
        # the names a class's objects answer to, sorted by their bytes, each with its kind
        es = ["{ptr, i64} {ptr " + d.refs[j] + ", i64 " + d.items[j].v + "}" for j in range(len(d.refs))]
        return f"{d.name} = internal constant [{len(es)} x {{ptr, i64}}] [{', '.join(es)}], align 8"
    if d.kind == "classfields":
        # the fields of an object's __dict__ in their order: name, type descriptor, byte offset in
        # the class's layout (d.text) and that of its "is assigned" flag (-1: always assigned)
        es: list[str] = []
        for j in range(len(d.refs) // 2):
            off = f"ptrtoint (ptr getelementptr ({d.text}, ptr null, i32 0, i32 {d.items[2 * j].v}) to i64)"
            fl = d.items[2 * j + 1].v
            flo = "-1" if fl == "-1" else f"ptrtoint (ptr getelementptr ({d.text}, ptr null, i32 0, i32 {fl}) to i64)"
            es.append("{ptr, ptr, i64, i64} {ptr " + d.refs[2 * j] + ", ptr " + d.refs[2 * j + 1] + ", i64 " + off + ", i64 " + flo + "}")
        return f"{d.name} = internal constant [{len(es)} x {{ptr, ptr, i64, i64}}] [{', '.join(es)}], align 8"
    fail(f"internal error: no LLVM lowering for module data {d.kind}", 0)
    return ""


def gen_cextern(self, f: FnInfo) -> None:
    # @ffi.extern: the program calls @f.<name> as any function, an internal stub that checks and
    # narrows C integers (OverflowError), passes a str as its bytes (const char *, NUL-terminated;
    # ValueError for a NUL in it) and a list[float] or list[c_int64] as its items (double *,
    # int64_t *: runtime.c's List.a, which C reads and writes in place for the call; the collector
    # moves nothing, and no subset code runs until the call returns, so the list cannot grow
    # meanwhile), and copies a returned char * (NULL: None, or ValueError). It calls
    # the C function through @ffi.fp.<f.ll>, which the def statement set as ctypes.CDLL would find it, in
    # the library's own handle (pys_c_bind: see stmt's defaults); only a GLUE module (lib/pyobj.py)
    # calls its functions directly, libpython's ("python") and those of the C glue linked in ("")
    self.line = f.node.line
    sym = f.csym[1:]
    direct = f.mod in GLUE
    if f.lib == "python" and not direct:
        self.err('@extern("python") is reserved for Pystachy\'s lib/pyobj.py: import pyobj to call CPython')
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
        elif c == "list[float]" or c == "list[c_int64]":
            code.append(f"  %l{j} = getelementptr inbounds {{i64, i64, ptr}}, ptr %a{j}, i64 0, i32 2")  # (List.a: runtime.c's {len, cap, a})
            code.append(f"  %p{j} = load ptr, ptr %l{j}")
            cts.append("ptr")
        elif c == "float":
            code.append(f"  %p{j} = bitcast double %a{j} to double")  # (as it is: -0.0, inf and nan too)
            cts.append("double")
        elif c == "c_float":
            code.append(f"  %p{j} = fptrunc double %a{j} to float")  # (to the nearest float, ties to even; too large: an infinity)
            cts.append("float")
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
    r = "ptr" if c in ("str", "opt[str]") else "double" if c == "float" else "float" if c == "c_float" else "void" if c == "None" else CTYPES[c].split(":")[0]
    rr = r[r.find(" ") + 1 :] + " " + r[: r.find(" ")] if " " in r else r  # (a result's attribute comes first: zeroext i32)
    cl = f"call {rr} {f.csym if direct else '%fp'}({', '.join(args)})"
    if not direct:
        code.insert(0, f"  %fp = load ptr, ptr @ffi.fp.{f.ll[1:]}")
    if r == "void":
        code.extend([f"  {cl}", "  ret void"])
    elif c == "str" or c == "opt[str]":
        self.runtime("pys_cstr")
        code.extend([f"  %r = {cl}", f"  %s = call ptr @pys_cstr(ptr %r, i64 {1 if c == 'str' else 0})", "  ret ptr %s"])
    elif c == "float":
        code.extend([f"  %r = {cl}", "  ret double %r"])
    elif c == "c_float":
        code.extend([f"  %r = {cl}", "  %x = fpext float %r to double", "  ret double %x"])  # (exactly)
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
        # one the compiler or the runtime calls too (fabs, memchr, ...): RUNTIME's types, declared from RUNTIME
        e = RtFn(RTSYM[sym]).ll
        if tys != e:
            self.err(f"C function {sym} is declared as {tys[0]}({', '.join(tys[1:])}), but Pystachy's runtime calls it as {e[0]}({', '.join(e[1:])})")
        if direct:
            self.runtime(sym)
    elif sym in self.csyms:
        if self.csyms[sym] != decl:
            self.err(f"C function {sym} is declared again with other types: {self.csyms[sym][8:]} at line {self.csymline[sym]}, {decl[8:]} here")
    else:
        self.csyms[sym] = decl
        self.csymline[sym] = f.node.line
    if direct:
        # (the C function itself, declared once for the calls that name it)
        decl = decl if sym not in RTSYM and sym not in self.cdirect else ""
        self.cdirect[sym] = True
    else:
        # (the C function's address, and the library and symbol pys_c_bind looks it up by)
        x = f.ll[1:]
        decl = f"@ffi.fp.{x} = internal global ptr null\n@ffi.lib.{x} = private unnamed_addr constant [{len(f.lib) + 1} x i8] c\"{llstr(f.lib)}\\00\"\n@ffi.sym.{x} = private unnamed_addr constant [{len(sym) + 1} x i8] c\"{llstr(sym)}\\00\""
        if len(LINKDL) == 0:
            LINKDL.append("dl")
    self.externs[f.ll] = (decl + "\n" if decl != "" else "") + f"define internal {lt(f.ret)} {f.ll}({', '.join(ps)}) {{\n" + "\n".join(code) + "\n}"
    if f.lib == "python" and f.lib not in LIBS:
        LIBS.append(f.lib)

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
        if "$" not in ci.name and not ci.name.startswith("_") and short(ci.name) == ci.name:
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
    # pys_obj_<op>(class id, [op code,] a, b), called by the runtime for "O<id>" descriptors;
    # pys_obj_eq(-1 - id, a, 0) is the hash of a, for "H<id>" (hcls: hash_helper). Only a
    # class that a descriptor compares (ocmp) has @o.eq and @o.cmp
    r = "ptr" if op == "repr" else "i64"
    hs = [c for c in self.hcls] if op == "eq" else []
    cs = [c for c in self.ocls if op == "repr" or c in self.ocmp]
    self.out.append(f"define {r} @pys_obj_{op}(i64 %c, {'i64 %op, ' if op == 'cmp' else ''}i64 %a, i64 %b) {{")
    self.out.append("entry:")
    self.out.append("  %pa = inttoptr i64 %a to ptr")
    self.out.append("  %pb = inttoptr i64 %b to ptr")
    cases = [f"i64 {self.ocls[c]}, label %k{self.ocls[c]}" for c in cs] + [f"i64 {-1 - self.ocls[c]}, label %h{self.ocls[c]}" for c in hs]
    self.out.append(f"  switch i64 %c, label %none [{' '.join(cases)}]")
    for c in cs:
        i = self.ocls[c]
        self.out.append(f"k{i}:")
        if op == "repr":
            self.out.append(f"  %r{i} = call ptr @o.repr.{c}(ptr %pa, ptr %pb)")
            self.out.append(f"  ret ptr %r{i}")
        else:
            self.out.append(f"  %r{i} = call i1 @o.{op}.{c}({'i64 %op, ' if op == 'cmp' else ''}ptr %pa, ptr %pb)")
            self.out.append(f"  %z{i} = zext i1 %r{i} to i64")
            self.out.append(f"  ret i64 %z{i}")
    for c in hs:
        i = self.ocls[c]
        self.out.append(f"h{i}:")
        self.out.append(f"  %x{i} = call i64 @o.hash.{c}(ptr %pa)")
        self.out.append(f"  ret i64 %x{i}")
    self.out.append("none:")
    self.out.append("  unreachable")
    self.out.append("}")

def gen_gen_module(self) -> list[str]:
    # what generators need of the module (docs/internals.md#generators): LLVM's coroutine
    # intrinsics, and pys.gen.drop, which closes a generator a loop owns as the loop is left and
    # destroys it. Closing one suspended where that runs code of its (state 1) resumes it with
    # the close command, which raises GeneratorExit at its yield; its landing block reports
    # anything else it raises, and if it yields instead, CPython's RuntimeError is reported here
    o: list[str] = [
        "declare token @llvm.coro.id(i32, ptr, ptr, ptr)", "declare i1 @llvm.coro.alloc(token)",
        "declare i64 @llvm.coro.size.i64()", "declare ptr @llvm.coro.begin(token, ptr)",
        "declare i8 @llvm.coro.suspend(token, i1)", "declare ptr @llvm.coro.free(token, ptr)",
        "declare i1 @llvm.coro.end(ptr, i1, token)", "declare void @llvm.coro.resume(ptr)",
        "declare void @llvm.coro.destroy(ptr)", "declare ptr @llvm.coro.promise(ptr, i32, i1)"]
    if not self.gendrops:
        return o
    return o + [
        "define internal void @pys.gen.drop(ptr %h) {",
        "entry:",
        "  %p = call ptr @llvm.coro.promise(ptr %h, i32 8, i1 false)",
        f"  %sa = getelementptr i64, ptr %p, i64 {GENSTATE}",
        "  %s = load i64, ptr %sa",
        f"  %c = icmp eq i64 %s, {GENCLEAN}",
        "  br i1 %c, label %close, label %done",
        "close:",
        f"  %ca = getelementptr i64, ptr %p, i64 {GENCMD}",
        "  store i64 1, ptr %ca",
        f"  store i64 {GENRUN}, ptr %sa",
        "  %x = call ptr @pys_exc_handled()",
        "  call void @llvm.coro.resume(ptr %h)",
        "  call void @pys_exc_restore(ptr %x)",
        "  %s2 = load i64, ptr %sa",
        f"  %ok = icmp eq i64 %s2, {GENDONE}",
        "  br i1 %ok, label %done, label %ignored",
        "ignored:",
        f"  %na = getelementptr i64, ptr %p, i64 {GENNAME}",
        "  %n = load ptr, ptr %na",
        "  call void @pys_gen_ignored(ptr %n, ptr %p)",
        "  br label %done",
        "done:",  # (finished, as close() leaves it, for a yield from's consumer that holds it too)
        f"  store i64 {GENDONE}, ptr %sa",
        "  call void @llvm.coro.destroy(ptr %h)",
        "  ret void",
        "}"]

def gen_lower_module(self) -> str:
    hdr: list[str] = ["; generated by pystachy"]
    for ci in self.classes.values():
        if ci.name in self.tmpl:
            continue  # (a class template's objects are its specializations')
        if ci.name == RANGEC and not self.rangeused:
            continue  # (lib's class of range objects, which a program that may make one loads: of no code here)
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
    if self.coros or self.gendrops:
        hdr.extend(self.gen_module())
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
    # (atexit's callbacks: pys_finish runs the Callable its _hook holds, once its module has run)
    hook = "@g.atexit$_hook" if any(g.v == "@g.atexit$_hook" for g in self.globs) else ""
    if hook != "":
        hdr.append(runtime_decl("exit_hook"))
    hdr.append(runtime_decl("frameaddress"))
    if self.eh:
        hdr.append(runtime_decl("eh_on"))
    hdr.append("define i32 @main(i32 %argc, ptr %argv) {")
    hdr.append("  %sb = call ptr @llvm.frameaddress.p0(i32 0)")
    hdr.append(f"  call void @pys_init(i32 %argc, ptr %argv, ptr %sb, ptr @pys.roots, i64 {len(self.gcroots)})")
    if self.eh:
        hdr.append("  call void @pys_eh_on()")  # (from now on, the runtime raises exceptions)
    if hook != "":
        hdr.append(f"  call void @pys_exit_hook(ptr {hook})")
    hdr.append("  call void @main.init()")
    hdr.append("  call void @pys_finish()")
    hdr.append("  ret i32 0")
    hdr.append("}")
    return "\n".join(hdr) + "\n"
