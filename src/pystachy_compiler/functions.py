"""Functions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import globals_in, lambda_flags, local_names, nonlocal_decls, str_appends
from src.pystachy_compiler.ir import Blk, FnInfo, IFn, Try, Val
from src.pystachy_compiler.local_versions import local_versions
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import CTYPES, RTSYM
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    RtFn,
    clone,
    is_list,
    is_opt,
    lt,
    rename,
    rt_subset,
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
    self.appends = {}
    self.owned = {}
    self.lcs = []
    self.lct = []
    self.lcsoft = []
    self.nonevars = {}
    self.nonesites = {}
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
    if not self.modlevel and not self.rtmode and len(f.node.kids) >= 3:
        versioned = local_versions(f, body)
        # Template instances share their declaration. Mark this instance's
        # eligible stores without changing another instance's AST.
        if len(versioned) > 0:
            body = versioned
            f.node = clone(f.node)
            f.node.kids[2].kids = body
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
        if not self.rtmode:
            str_appends(body, self.appends)  # (those that are str locals get an owned flag: alloca)
    for i in range(len(f.params)):
        t = f.ptypes[i]
        if t == "None":
            # an argument that is None: the parameter is not passed, and reads of it are None
            self.nonevars[f.params[i]] = 0
            continue
        self.fn.ps.append(i)
        self.mem_store(Val(self.alloca(t, f.params[i]), "*" + t), Val(f"%a{i}", t))
        if f.params[i] in self.lflag:
            self.mem_store(Val(self.lflag[f.params[i]], "*bool"), Val("true", "bool"))  # (a parameter that del unbinds)
    if f.clo >= 0:
        # a closure: the variables it takes are the cells its env holds
        c = self.closures[f.clo]
        for cv in c.nlw:
            self.nlw[cv] = True
        env = self.mem_load(Val(self.lreg['.env'], "*env")).v
        for i in range(len(c.caps)):
            if c.ctypes[i] == "None":
                self.nonevars[c.caps[i]] = 0  # (a parameter whose argument is None: it reads as None)
                continue
            a = self.maddr('%ptr', env, f'{i}', True)
            self.lreg[c.caps[i]] = self.mload('%ptr', a)
            self.ltype[c.caps[i]] = c.ctypes[i]
        for j in range(len(c.iflags)):
            a = self.maddr('%ptr', env, f'{len(c.caps) + len(c.defs) + j}', True)
            self.iflag[c.iflags[j]] = self.mload('%ptr', a)
    self.none_ends()
    if f.gen:
        self.gen_begin(f)  # (a generator: a call makes it, and runs none of the code below)
    if f.ll.startswith("@init."):
        # a module's code runs once, when the first import of it runs
        done = f.ll + ".done"
        self.global_var(done, "bool")
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.mem_load(Val(done, "*bool")).v, l1, l2)
        self.place(l1)
        self.ret_(Val("null", "None"))
        self.place(l2)
        self.mem_store(Val(done, "*bool"), Val("true", "bool"))
        # A retry after a failed initialization creates a fresh module in CPython. Its import
        # aliases start unbound too, even if the failed attempt had reached their imports.
        flags: dict[str, bool] = {}
        pending = [n for n in body]
        while len(pending) > 0:
            n = pending.pop()
            if n.kind == "bound":
                for imported_name in n.s.split():
                    flags[imported_name] = True
            elif n.kind != "def" and n.kind != "lambda":
                pending.extend(n.kids)
        for imported_name in flags:
            self.mem_store(Val(self.imp_flag(imported_name, True), "*bool"), Val("false", "bool"))
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
    if f.gen:
        self.gen_end(f)
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
        self.mem_store(Val(f"{f.ll}.done", "*bool"), Val("false", "bool"))
        self.throw(e)
    if not self.term:
        if f.ret == "None" or (f.infer and f.ret in self.classes) or is_opt(f.ret) or (self.retann and f.ret != "" and self.optional(f.ret) == f.ret and self.ann_none(f.node.kids[1], [])):
            # (a template's function that ends without a return, or one returning T | None: None;
            # also C | None for a class C, whose type, C's, includes None without showing it)
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
    # an @extern signature's type: "float", "c_float", "str", "None", "opt[str]" or a CTYPES name, or a list
    # taken as its items, "list[float]" (double *) or "list[c_int64]" (int64_t *): the 8-byte slots
    # of runtime.c's List hold a float's bits and an int as they are, so C sees them in place
    ref = self.imported_ref(a)
    c = ref[4:] if ref.startswith("ffi.") else ""
    if c in CTYPES or c == "c_float" or (c == "c_buf" and what == "takes"):
        return c
    if what == "takes" and is_list(t) and a.kind == "index" and a.kids[1].kind in ("name", "attr"):
        ref = self.imported_ref(a.kids[1])
        e = a.kids[1].s if a.kids[1].kind == "name" else ref
        ce = ref[4:] if ref.startswith("ffi.") else ""
        if ce == "c_int64" or ce == "c_ssize_t":
            return "list[c_int64]"
        if t == "list[float]" and ce == "":  # (not list[c_float], also a list[float] to the subset: C would read floats)
            return "list[float]"
        if e == "int":
            self.err(f"C function {f.name}() takes list[int]: say which C integer type its items are (list[ffi.c_int64], which C gets as an int64_t *)")
        if ce in CTYPES or ce == "c_float":
            self.err(f"C function {f.name}() takes list[{e}]: C gets a list's items in place, 8 bytes each, as a double * (list[float]) or an int64_t * (list[ffi.c_int64]); copy them into the C type with a shim")
    if t == "int":
        self.err(f"C function {f.name}() {what} int: say which C integer type (ffi.c_int, c_uint, c_int64, c_uint64, c_size_t, c_ssize_t or c_void_p)")
    if t in ("float", "str") or (what == "returns" and t in ("None", "opt[str]")):
        return t
    self.err(f"C function {f.name}() {what} {typestr(t)}: an @extern function {'takes a C integer type, float, str, list[float] or list[ffi.c_int64]' if what == 'takes' else 'returns a C integer type, float or str, str | None or None'}")
    return ""

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
