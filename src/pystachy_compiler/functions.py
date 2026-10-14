"""Functions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import globals_in, lambda_flags, local_names, nonlocal_decls
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Try, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import CTYPES, LINKDL, RTSYM
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    RtFn,
    clone,
    is_opt,
    llstr,
    lt,
    rename,
    rt_subset,
    runtime_decl,
    takes_self,
    typestr,
)


def gen_enter(self, f: FnInfo, body: list[Node]) -> None:
    # the code generator's state at the start of function f, whose statements are body
    self.fn = IFn(f)
    self.blk = self.fn.blocks[0]
    self.ltype = {}
    self.lreg = {}
    self.gdecl = {}
    self.assigned = {}
    self.compvars = {}
    self.loops = []
    self.exits = []
    self.wdepth = []
    self.handler = ""
    self.excs = []
    self.shadows = []
    self.n = 0
    self.cur = "entry"
    self.term = False
    self.ret = f.ret
    self.retann = f.node.kind == "def" and f.node.kids[1].kind != "noann"
    self.nn = {}
    self.selfname = ""
    self.uflags = f.uflags
    self.lflag = {}
    self.iflag = {}
    self.lcs = []
    self.lct = []
    self.nonevars = {}
    self.narrowed = {}
    self.lkk = {}
    self.branch = 0
    self.cells = {}
    self.nlw = {}
    self.curfn = f
    self.line = f.node.line
    if not self.modlevel:
        local_names(body, self.assigned)
        globals_in(body, self.gdecl)  # (global holds for the whole function, also from a dead branch)

def gen_materialize(self, f: FnInfo) -> None:
    # Flow annotates nodes and cls substitution renames them: each compiled inherited
    # method needs its own body, but an unused one retains only its declaration header.
    if not f.pending:
        return
    f.pending = False
    f.node.kids[2] = clone(f.orig.kids[2])
    rename(f.node.kids[2], f.orig.kids[0].kids[0].s, f.cls)
    mod = self.flowmod
    self.flowmod = f.mod
    ctx = self.flowctx[f.mod]
    self.flow_function(f, ctx[0], ctx[1], ctx[2])
    self.flowmod = mod

def gen_function(self, f: FnInfo, body: list[Node]) -> None:
    if f.pending:
        self.materialize(f)
        body = f.node.kids[2].kids
    if f.cls != "" and self.classes[f.cls].bad != "":
        self.err(self.classes[f.cls].bad)
    if f.bad != "" and not f.generic:
        self.err(f.bad)
    self.compiled[f.ll] = True
    self.building[f.ll] = True
    sel = self.selfcls
    self.selfcls = ""  # (its annotations name its class's types: f.cls's, see tvar)
    self.enter(f, body)
    if takes_self(f):
        # callers check the receiver, so self is never None inside a method
        self.nn["%a0"] = True
        if f.params[0] not in self.assigned:
            self.selfname = f.params[0]
    if not self.modlevel:
        # the variables that the defs and lambdas in it take: each lives in a cell, which the
        # closures share with it (see closure)
        for cv in self.cellvars(f, body):
            self.cells[cv] = self.rt("pys_alloc", "ptr", ["i64 8"])
        lf: dict[str, bool] = {}
        for st in body if f.clo < 0 or self.closures[f.clo].name != "<lambda>" else []:
            lambda_flags(st, False, lf)
        for nm in lf:
            # (the flag of a name its import binds that a lambda in it reads: a cell, which the
            # lambda's env holds too, see imp_flag)
            self.iflag[nm] = self.rt("pys_alloc", "ptr", ["i64 8"])
        if len(self.cells) > 0:
            nl: dict[str, bool] = {}
            for st in body:
                nonlocal_decls(st, nl)
            for cv in self.cells:
                if cv in nl:
                    self.nlw[cv] = True
    for i in range(len(f.params)):
        t = f.ptypes[i]
        if t == "None":
            # an argument that is None: the parameter is not passed, and reads of it are None
            self.nonevars[f.params[i]] = 0
            continue
        self.fn.ps.append(i)
        self.emit(f"store {lt(t)} %a{i}, ptr {self.alloca(t, f.params[i])}")
        if f.params[i] in self.lflag:
            self.emit(f"store i1 true, ptr {self.lflag[f.params[i]]}")  # (a parameter that del unbinds)
    if f.clo >= 0:
        # a closure: the variables it takes are the cells its env holds
        c = self.closures[f.clo]
        for cv in c.nlw:
            self.nlw[cv] = True
        env = self.ins(f"load ptr, ptr {self.lreg['.env']}")
        for i in range(len(c.caps)):
            if c.ctypes[i] == "None":
                self.nonevars[c.caps[i]] = 0  # (a parameter whose argument is None: it reads as None)
                continue
            a = self.ins(f"getelementptr inbounds ptr, ptr {env}, i64 {i}")
            self.lreg[c.caps[i]] = self.ins(f"load ptr, ptr {a}")
            self.ltype[c.caps[i]] = c.ctypes[i]
        for j in range(len(c.iflags)):
            a = self.ins(f"getelementptr inbounds ptr, ptr {env}, i64 {len(c.caps) + len(c.defs) + j}")
            self.iflag[c.iflags[j]] = self.ins(f"load ptr, ptr {a}")
    self.none_ends()
    if f.ll.startswith("@init."):
        # a module's code runs once, when the first import of it runs
        done = f.ll + ".done"
        self.global_var(done, "i1")
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ins(f"load i1, ptr {done}"), l1, l2)
        self.place(l1)
        self.ret_(Val("null", "None"))
        self.place(l2)
        self.emit(f"store i1 true, ptr {done}")
    hm = ""
    mark = Val("", "")
    slot = ""
    if f.ll.startswith("@init.") and self.eh:
        # an exception that leaves a module's code leaves the module not imported, as CPython
        # removes it from sys.modules: a landing block around the code clears its done flag
        # and throws again, so that a later import runs the code again
        mark = Val(self.rt("pys_try_mark", "i64", []), "int")
        slot = self.alloca("exc", "")
        hm = self.label()
        tr = Try(self.label())
        tr.landing = hm
        self.fn.tries.append(tr)
        self.handler = hm
        self.place(tr.body)
    self.stmts(body)
    if f.ret == "":
        f.ret = "None"  # a template's function without a return statement that has a value
        f.noret = f.infer and self.term
        for b in self.fn.blocks:
            for x in b.code:
                f.noret = f.noret and x.op != "ret" and x.op != "ret.none"
    if f.infer:
        # its returns of None, before it was known what it returns: None for an object, and
        # str, list, dict or tuple T make it return T | None (ret.none is lowered from f.ret)
        for b in self.fn.blocks:
            for x in b.code:
                if x.op == "ret.none":
                    if f.ret != "None" and self.optional(f.ret) == "":
                        self.err(self.nonemix(f, f.ret))
                    if f.ret != self.optional(f.ret) and f.ret != "None":
                        self.reopt(self.optional(f.ret))
    if hm != "":
        if not self.term:
            self.ret_(Val("null", "None"))
        self.handler = ""
        e = self.landing(hm, slot, mark)
        self.emit(f"store i1 false, ptr {f.ll}.done")
        self.throw(e)
    if not self.term:
        if f.ret == "None" or (f.infer and f.ret in self.classes) or is_opt(f.ret):
            # (a template's function that ends without a return, or one returning T | None: None)
            self.ret_(Val("null", f.ret))
            if len(self.fn.cold) > 0:
                # the jump to the first cold block that follows is a block of its own, which
                # LLVM starts after a terminator, without a label
                self.blk = Blk("")
                self.fn.blocks.append(self.blk)
                self.term = False
        else:
            self.raise_("RuntimeError", self.sconst(f"{short(f.name)}() ended without returning a value"))
    for key in self.fn.cold:
        self.place(self.fn.cold[key])
        msg = key
        if key in self.fn.coldh:
            self.blk.handler = self.fn.coldh[key]
            msg = key[len(self.fn.coldh[key]) + 1 :]
        i = msg.find(": ")
        self.raise_(msg[:i], self.sconst(msg[i + 2 :]))
    if f.export:
        # the runtime's ABI: what runtime.c's prototype says, and what programs call: RUNTIME's
        # types, for an operation the compiler lowers to it
        for t in f.ptypes + [f.ret]:
            if t == "bool" or t == "":
                self.err(f"runtime function {f.name}() takes or returns {typestr(t) if t != '' else 'an untyped value'}: the runtime ABI passes bools as int")
        have = [lt(f.ret)] + [lt(f.ptypes[j]) for j in self.fn.ps]
        if f.ll[1:] in RTSYM and have != RtFn(RTSYM[f.ll[1:]]).ll:
            want = RtFn(RTSYM[f.ll[1:]]).ll
            self.err(f"{f.name}() is defined as {have[0]}({', '.join(have[1:])}), but the compiler calls it as {want[0]}({', '.join(want[1:])}) (RUNTIME's {RTSYM[f.ll[1:]]})")
        ts = [f.ret] + [f.ptypes[j] for j in self.fn.ps]
        if f.ll[1:] in RTSYM and rt_subset(RTSYM[f.ll[1:]], ts) != "":
            # (the same LLVM types, but another layout: a tuple of two strs for one of three)
            self.err(f"{f.name}() is defined as {typestr(ts[0])}({', '.join([typestr(t) for t in ts[1:]])}), but the compiler calls it as {rt_subset(RTSYM[f.ll[1:]], ts)} (RUNTIME's {RTSYM[f.ll[1:]]})")
        self.untold(f, ts, "defined")
    del self.building[f.ll]
    self.selfcls = sel
    self.fn.n = self.n
    self.fns.append(self.fn)

def gen_extern_args(self, x: Node, more: bool) -> list[str]:
    # decorator x, @ffi.extern(lib, symbol=""): the library and the symbol ("" for the function's
    # own name), its arguments bound as CPython binds the twin's (by position or keyword, with its
    # TypeError for what that signature does not take), each a string literal with no NUL in it.
    # more: the def has another decorator too, or is async (an error, as a bare @extern is)
    bad = '@extern takes the library ("" for the process\'s own) and an optional symbol name, as string literals'
    if len(x.kids) == 0 or more:
        self.err(bad)
    names = ["lib", "symbol"]
    given: dict[str, Node] = {}
    npos = 0
    for a in x.kids[0].kids[1:]:
        if a.kind == "starred" or a.kind == "dstar":
            self.err(bad)
        if a.kind != "kw":
            if npos < 2:
                given[names[npos]] = a
            npos += 1
        elif a.s not in names:
            self.err(f"extern() got an unexpected keyword argument '{a.s}'")
        elif a.s in given:
            self.err(f"extern() got multiple values for argument '{a.s}'")
        else:
            given[a.s] = a.kids[0]
    if npos > 2:
        self.err(f"extern() takes from 1 to 2 positional arguments but {npos} were given")
    if "lib" not in given:
        self.err("extern() missing 1 required positional argument: 'lib'")
    r: list[str] = []
    for k in names:
        v = given.get(k, mk("str", "", x.line, []))
        if v.kind != "str":
            self.err(bad)
        if chr(0) in v.s:
            # (the C string would end there: ctypes raises ValueError for the library's, and looks the
            # symbol up only as far as it, where the program surely meant the whole name)
            why = "ctypes raises ValueError: embedded null byte" if k == "lib" else "C would look up only the name before it"
            self.err(f"@extern's {'library' if k == 'lib' else 'symbol'} has a NUL character in it: {why}")
        r.append(v.s)
    return r

def gen_externtype(self, a: Node, t: str, what: str, f: FnInfo) -> str:
    # an @extern signature's type: "float", "str", "None", "opt[str]" or a CTYPES name
    c = self.imported(a.s)[4:] if a.kind == "name" and self.imported(a.s).startswith("ffi.") else ""
    if c in CTYPES or (c == "c_buf" and what == "takes"):
        return c
    if t == "int":
        self.err(f"C function {f.name}() {what} int: say which C integer type (ffi.c_int, c_uint, c_int64, c_uint64, c_size_t, c_ssize_t or c_void_p)")
    if t in ("float", "str") or (what == "returns" and t in ("None", "opt[str]")):
        return t
    self.err(f"C function {f.name}() {what} {typestr(t)}: an @extern function {'takes' if what == 'takes' else 'returns'} a C integer type, float or str{', str | None or None' if what == 'returns' else ''}")
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

def gen_untold(self, f: FnInfo, ts: list[str], how: str) -> None:
    # a function of runtime mode that runtime.c calls or defines and RUNTIME does not name
    # (the dict's string hash, the format of a str): only LLVM's types check it (rtabi,
    # check_runtime), which tell int, float and a pointer apart, not a list from a str. So it
    # passes those alone
    if f.ll[1:] not in RTSYM:
        for t in ts:
            if t not in ("int", "float", "str", "None"):
                self.err(f"{f.name}() is {how} with {typestr(t)}, which RUNTIME has no entry to check: a function of runtime mode that the compiler does not call takes and returns int, float, str or None")

# ---- lowering: an IFn as LLVM text
