"""Flow component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import (
    bind_line,
    closure_free,
    collect,
    deleted,
    global_assigns,
    global_line,
    globals_in,
    lambda_def,
    local_names,
    name_nodes,
    scope_binds,
)
from src.pystachy_compiler.diagnostics import dynamic_program, shown
from src.pystachy_compiler.ir import ClassInfo, FnInfo
from src.pystachy_compiler.names import short
from src.pystachy_compiler.syntax import Node, mentions, mk
from src.pystachy_compiler.specs import NONEVAR
from src.pystachy_compiler.utils import is_const, numeric_identity


class Flow:
    # definite assignment over one scope: which reads may find their variable unassigned
    def __init__(self, tracked: dict[str, bool], defd: dict[str, bool]):
        self.tracked = tracked
        self.defd = defd  # names assigned on every path to here; " dead" marks unreachable code
        # every change to defd since the start, so that a branch is undone in the time it took
        # (not by copying defd): the key, and whether it was in defd before
        self.log: list[str] = []
        self.was: list[bool] = []
        # the innermost loop, if it is a while True (left only through break): what the states at
        # its breaks so far have in common (see fold)
        self.btrue = False
        self.bjoin: dict[str, bool] = {}  # the keys whose common state is not their state where the loop began: that state
        self.bany = False  # a break was folded
        self.bwas: dict[str, bool] = {}  # the keys changed in the loop: whether each was in defd where it began
        self.bnew: dict[str, bool] = {}  # the keys changed since the last break (or since the loop began)
        # the names the except clauses inside the innermost loop bind, and those the finally blocks
        # around them there may delete: a break unbinds them
        self.unb: list[str] = []
        self.marks: dict[str, bool] = {}
        self.call: dict[str, bool] = {}
        self.called = False
        # field mode, over __init__: which fields may be seen unassigned (".f" in defd = assigned)
        self.me = ""
        self.fields: list[str] = []
        self.unsafe: dict[str, bool] = {}
        # hasattr(self, "f") is the builtin (probes): it reads f's flag (probed: where f may be
        # unassigned), and f is assigned where it is true
        self.probes = False
        self.probed: dict[str, bool] = {}
        # in an exception class's __init__: the fields super().__init__() surely assigns, whether it
        # lets self escape, and whether this __init__ does
        self.sup: list[str] = []
        self.base = ""  # (the class's base, whose __init__ it may call as Base.__init__(self, ...))
        self.sbase = ""  # (the base of the class defining __init__, whose methods super().m(...) calls)
        self.leak = False
        self.escaped = False
        # the variables of the function analysed (its locals and those it takes from around it),
        # which a def or lambda in it takes when it reads them (Gen.fl_nested)
        self.scope: dict[str, bool] = {}

    def exposed(self) -> None:
        # self escapes or __init__ returns: fields not assigned yet may be read unassigned
        if " dead" not in self.defd:
            for f in self.fields:
                if "." + f not in self.defd:
                    self.unsafe[f] = True

    def put(self, k: str) -> None:
        if k not in self.defd:
            if self.btrue:
                self.touch(k, False)
            self.defd[k] = True
            self.log.append(k)
            self.was.append(False)

    def drop(self, k: str) -> None:
        if k in self.defd:
            if self.btrue:
                self.touch(k, True)
            del self.defd[k]
            self.log.append(k)
            self.was.append(True)

    def touch(self, k: str, was: bool) -> None:
        # k changes in a while True loop: the next break looks at it (see fold)
        if k not in self.bwas:
            self.bwas[k] = was
        self.bnew[k] = True

    def undo(self, mark: int) -> None:
        # back to the state when the log had mark entries
        while len(self.log) > mark:
            k = self.log.pop()
            if self.btrue:
                self.bnew[k] = True
            if self.was.pop():
                self.defd[k] = True
            else:
                del self.defd[k]

    def since(self, mark: int) -> dict[str, bool]:
        # the state now, as the keys changed since the log had mark entries, each with whether
        # it is in defd (the other keys are as they were then), and " dead" in any case
        out: dict[str, bool] = {}
        for i in range(mark, len(self.log)):
            out[self.log[i]] = self.log[i] in self.defd
        out[" dead"] = " dead" in self.defd
        return out

    def fold(self) -> None:
        # a break leaves the innermost loop, a while True, in the state here: bjoin keeps what
        # the states at its breaks have in common, for the keys where that is not their state
        # where the loop began. Only the keys changed since the last break need a look: the
        # others are as they were there, so what they have in common stays
        for k in self.bnew:
            v = k in self.defd and (not self.bany or (self.bjoin[k] if k in self.bjoin else self.bwas[k]))
            if v != self.bwas[k]:
                self.bjoin[k] = v
            elif k in self.bjoin:
                del self.bjoin[k]
        self.bnew = {}
        self.bany = True

    def join(self, other: dict[str, bool], mark: int) -> None:
        # another path reaches here, in the state since(mark) gave for it: a name stays assigned
        # if it is on both paths (or on the one that is not dead)
        if other[" dead"]:
            return
        if " dead" in self.defd:
            # only the other path goes on: the state at mark, changed as it changed it
            self.undo(mark)
            for k in other:
                if other[k]:
                    self.put(k)
                else:
                    self.drop(k)
            return
        pre: dict[str, bool] = {}
        for i in range(mark, len(self.log)):
            if self.log[i] not in pre:
                pre[self.log[i]] = self.was[i]
        end = len(self.log)
        for k in other:
            if not other[k]:
                self.drop(k)
        for k in pre:
            if not pre[k] and k not in other:
                self.drop(k)
        # the log since mark keeps one entry for each key not in its state at mark: the changes
        # that cancel out (a key assigned on this path alone) are not looked at again by the
        # joins of the enclosing ifs (an elif chain would cost its length times its last branch)
        for i in range(end, len(self.log)):
            if self.log[i] not in pre:
                pre[self.log[i]] = self.was[i]
        n = mark
        for k in pre:
            if (k in self.defd) != pre[k]:
                self.log[n] = k
                self.was[n] = pre[k]
                n += 1
        while len(self.log) > n:
            self.log.pop()
            self.was.pop()

    def probe(self, e: Node) -> str:
        # the field that test e, hasattr(self, "f") (probes), finds assigned when true, or ""
        if self.probes and e.kind == "call" and len(e.kids) == 3 and e.kids[0].kind == "name" and e.kids[0].s == "hasattr" and e.kids[1].kind == "name" and e.kids[1].s == self.me and e.kids[2].kind == "str" and e.kids[2].s in self.fields:
            return e.kids[2].s
        return ""


# ---------------------------------------------------------------- code generator
def gen_flow_program(self, top: list[Node], mod: str, mfns: list[FnInfo], mcls: list[ClassInfo], first: bool) -> None:
    # one module: its top-level code, functions (mfns) and classes' methods (mcls); the first
    # module's (first) also checks the program's imports
    self.flowmod = mod
    fns: list[FnInfo] = []
    for f in mfns:
        fns.append(f)
    for ci in mcls:
        for f in ci.methods.values():
            if f.cls == ci.name:
                fns.append(f)
    gl: dict[str, bool] = {}
    collect(top, gl)
    for st in top:
        if st.kind == "def":
            gl[st.s] = True  # (a decorated def's name: what its decorators give)
    for st in top if mod == "" and self.ext != "" else []:
        one: dict[str, bool] = {}
        collect([st], one)
        for nm in one:
            if nm not in self.extvars:
                self.extvars[nm] = st.line  # (pystachy ext: where the module binds it)
    for f in fns:
        if f.pending:
            continue  # its defining method already contributes the same global assignments
        ga: dict[str, bool] = {}
        global_assigns(f.node.kids[2].kids, ga)
        for nm in ga:
            if nm not in gl:
                self.fglobals[nm] = True
            gl[nm] = True
    # one binding per name: a function, a class, an import or a variable
    for nm in gl:
        if nm in self.funcs or nm in self.classes or (nm in self.imports and not self.imports[nm].startswith("__future__")):
            # (reported where the module binds it as a variable, else where a function of it
            # assigns it as a global, else at its decorated def)
            ln = bind_line(top, nm)
            for f in fns:
                ga = {}
                if ln < 0 and not f.pending:
                    global_assigns(f.node.kids[2].kids, ga)
                if nm in ga:
                    ln = global_line(f.node.kids[2].kids, nm)
                    ln = f.node.line if ln < 0 else ln
            for st in top:
                if ln < 0 and st.kind == "def" and st.s == nm:
                    ln = st.line
            self.line = ln if ln >= 0 else self.line
            self.err(f"'{nm}' is bound both as a variable and as a function, class or import (not supported)")
    for nm in self.imports if first else {}:
        # (those of every module, which no module's flow changes: once)
        if nm in self.funcs or nm in self.classes:
            self.err(f"'{nm}' is bound both by an import and by a def or class (not supported)")
    for nm in gl:
        self.mvars[nm] = True
    # def and class statements bind their names when they run: calls that may come first are checked
    for f in mfns:
        gl[f.name] = True
    for ci in mcls:
        gl[ci.name] = True
    mfl = Flow(gl, {})
    self.fvars = {}
    for st in top:
        # (a statement inside a compound one calls user code only if the compound one does)
        if not mfl.called and self.user_call(st):
            mfl.called = True
            mfl.call = dict(mfl.defd)
        self.fl_stmt(mfl, st)
    for nm in mfl.marks:
        self.gflag[nm] = True
    # functions run only from module code: globals assigned before its first call into user
    # code stay assigned while any function runs
    safe = mfl.call if mfl.called else gl
    dels: dict[str, bool] = {}
    deleted(top, dels)
    if mod != "" and " dead" not in mfl.defd:
        # an imported module's functions also run after its code, from other modules' code
        after: dict[str, bool] = {}
        for nm in safe:
            if nm in mfl.defd:
                after[nm] = True
        safe = after
    if mod != "":
        for nm in gl:
            if nm not in safe or nm in dels:
                self.late[nm] = True
                self.gflag[nm] = True
    self.flowctx[mod] = [gl, safe, dels]
    for d in self.flowlater:
        self.flow_body(d, {})  # (the lambdas of module code: see fl_nested)
    self.flowlater = []
    for f in fns:
        if f.pending:
            # A later materialization may mark reads of the substituted subclass name.
            # Reserve its flag before module code is emitted, which sets it at the class.
            if f.cls not in safe or f.cls in dels:
                self.gflag[f.cls] = True
        else:
            self.flow_function(f, gl, safe, dels)
    for ci in mcls:
        self.fl_fields(ci)

def gen_flow_function(self, f: FnInfo, gl: dict[str, bool], safe: dict[str, bool], dels: dict[str, bool]) -> None:
    body = f.node.kids[2].kids
    loc: dict[str, bool] = {}
    decl: dict[str, bool] = {}
    local_names(body, loc)
    globals_in(body, decl)
    # the analysis looks up only the names the body mentions, and each name's state is
    # independent of the others': it tracks those alone, not every global of the module
    refs: dict[str, bool] = {}
    for st in body:
        name_nodes(st, refs)
    tracked: dict[str, bool] = {}
    defd: dict[str, bool] = {}
    for nm in refs:
        if nm in gl or nm in loc:
            tracked[nm] = True
        if nm in gl and nm in safe and nm not in dels and (nm not in loc or nm in decl):
            defd[nm] = True
    fdels: dict[str, bool] = {}
    deleted(body, fdels)
    for nm in f.params:
        defd[nm] = True
        if nm in fdels:
            tracked[nm] = True  # (a parameter that del unbinds)
    fl = Flow(tracked, defd)
    fl.scope = dict(loc)
    for nm in f.params:
        fl.scope[nm] = True
    for nm in decl:
        fl.scope.pop(nm, False)
    self.fl_stmts(fl, body)
    for nm in fl.marks:
        if (nm in loc or nm in fdels) and nm not in decl:
            f.uflags[nm] = True
        else:
            self.gflag[nm] = True

def self_fields(n: Node, me: str, fields: list[str], out: dict[str, bool]) -> bool:
    # whether code n uses the name me only as me.f, of a field f (each kept in out)
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == me:
        if n.s not in fields:
            return False
        out[n.s] = True
        return True
    if (n.kind == "name" and n.s == me) or (n.kind == "deco" and (n.s == me or n.s.startswith(me + "."))):
        return False
    for k in n.kids:
        if not self_fields(k, me, fields, out):
            return False
    return True


def gen_fl_super(self, fl: Flow, m: str) -> bool:
    # super().m(...) in __init__ (field mode): whether self escapes no further than to the fields
    # it reads, which are marked. super() dispatches statically: the method m of the base (or
    # BaseException's __str__ or __repr__, which read only hidden fields). One that uses self only
    # as self.f, of fields f, reads only those (as a closure does, fl_nested); any other use
    # (passing self on, self.m, str(self), super()) may call code that reads any field
    if fl.sbase not in self.classes or m not in self.classes[fl.sbase].methods:
        return True
    f = self.classes[fl.sbase].methods[m]
    if f.deco != "":
        return True  # (a static or class method, given no object)
    if f.prop or f.synthetic or f.node.kind != "def" or len(f.params) == 0 or mentions(f.node.kids[2], ["super"]):
        return False
    used: dict[str, bool] = {}
    if not self_fields(f.node.kids[2], f.params[0], fl.fields, used):
        return False
    if " dead" not in fl.defd:
        for x in used:
            if "." + x not in fl.defd:
                fl.unsafe[x] = True
    return True


def gen_fl_nested(self, fl: Flow, n: Node) -> None:
    # a def or lambda n in the code fl analyses: its defaults and decorators run here. The
    # variables of fl's function that it reads must be assigned here, but a def's own name: a
    # closure reads them when it runs (Gen.closure), and those that may not be assigned are kept
    # in n.mchk. Its body is analysed as a function's is, with those variables assigned
    d = n if n.kind == "def" else lambda_def(n)
    for p in d.kids[0].kids:
        self.fl_expr(fl, p.kids[1])
    for dx in d.kids[3:] if n.kind == "def" else []:
        if dx.s != "async":
            self.fl_expr(fl, mk("call", "", dx.line, [self.deco_callee(dx, self.flowmod)]))  # (its decorators, called)
    free: dict[str, bool] = {}
    closure_free(d, free)
    if fl.me in free:
        # (in __init__, fl_fields: a function that takes self may run later and read the fields
        # not assigned here. One that uses self only as self.f, of fields f, reads only those (a
        # flag tests each); any other use may pass self anywhere, which reads any field)
        used: dict[str, bool] = {}
        if self_fields(d, fl.me, fl.fields, used):
            if " dead" not in fl.defd:
                for f in used:
                    if "." + f not in fl.defd:
                        fl.unsafe[f] = True
        else:
            fl.exposed()
            fl.escaped = True
    caps: dict[str, bool] = {}
    late: list[str] = []
    own = n.s if n.kind == "def" and not self.applies(n, False, fl.scope) else ""  # (a decorated def's name binds what the decorators give, later)
    for x in free:
        if x in fl.scope:
            caps[x] = True
            if x != own and x in fl.tracked and x not in fl.defd and " dead" not in fl.defd:
                late.append(x)
    if fl.me != "":
        # field mode (fl_fields): flow_function's pass over __init__ has set n.mchk and marked
        # n's body, with the variables it takes; this Flow tracks no variable, so a pass here
        # would clear n.mchk and mark the reads of those that share a global's name
        return
    n.mchk = " ".join(late)
    if n.kind == "def":
        fl.put(n.s)
    if self.flowmod in self.flowctx:
        self.flow_body(d, caps)
    else:
        self.flowlater.append(d)  # (module code's: once the module's state is known)

def gen_flow_body(self, d: Node, caps: dict[str, bool]) -> None:
    # the body of def d, a closure's, as flow_function analyses a function's: caps, the
    # variables it takes from around it, are assigned (fl_nested); the reads of its locals that
    # may find them unassigned are marked (Node.chk), which give its flags (Gen.closure_flags)
    ctx = self.flowctx[self.flowmod]
    gl = ctx[0]
    safe = ctx[1]
    dels = ctx[2]
    body = d.kids[2].kids
    loc: dict[str, bool] = {}
    decl: dict[str, bool] = {}
    local_names(body, loc)
    globals_in(body, decl)
    kinds: dict[str, str] = {}
    scope_binds(body, {}, kinds)
    for nm in kinds:
        if kinds[nm] == "nonlocal":
            loc.pop(nm, False)
    refs: dict[str, bool] = {}
    for st in body:
        name_nodes(st, refs)
    tracked: dict[str, bool] = {}
    defd: dict[str, bool] = {}
    for nm in refs:
        if nm in caps:
            continue
        if nm in gl or nm in loc:
            tracked[nm] = True
        if nm in gl and nm in safe and nm not in dels and (nm not in loc or nm in decl):
            defd[nm] = True
    fdels: dict[str, bool] = {}
    deleted(body, fdels)
    fl = Flow(tracked, defd)
    fl.scope = dict(loc)
    for p in d.kids[0].kids:
        defd[p.s] = True
        fl.scope[p.s] = True
        if p.s in fdels:
            tracked[p.s] = True
    for nm in caps:
        fl.scope[nm] = True
    for nm in decl:
        fl.scope.pop(nm, False)
    self.fl_stmts(fl, body)
    for nm in fl.marks:
        if not ((nm in loc or nm in fdels) and nm not in decl):
            self.gflag[nm] = True

def gen_fl_fields(self, ci: ClassInfo) -> None:
    # a field that may be read before __init__ assigns it gets an "is assigned" flag, so the
    # read raises AttributeError as in CPython instead of seeing 0 or null. The flags follow
    # the class's own fields; an exception class's struct begins with its base's, flags
    # included, since the base's methods work on its objects. Its constructor sets the hidden
    # fields; super().__init__() assigns what the base's __init__ surely does (and exposes self
    # if that lets it escape), as the constructor does when it calls the base's __init__
    if ci.flowed or ci.name in self.tmpl:
        return
    ci.flowed = True
    fl = Flow({}, {})
    for f in ci.fdefault:
        fl.defd["." + f] = True
    nb = 0
    if ci.base in self.classes:
        b = self.classes[ci.base]
        self.fl_fields(b)
        own = [f for f in ci.fields if f not in b.ftypes]
        extra = [f for f in b.fextra if f not in ci.ftypes or f in ci.fextra]
        ci.fields = [f for f in b.fields]
        for f in b.fields:
            ci.ftypes[f] = b.ftypes[f]  # (the places of its base's base's flags too)
        for k in range(b.nflag):
            ci.fields.append(f" {b.name}.{k}")  # (the place of one of the base's flags)
            ci.ftypes[ci.fields[-1]] = "bool"
        for k in range(b.nbox):
            ci.fields.append(f" {b.name}.box.{k}")
            ci.ftypes[ci.fields[-1]] = "dyn"
        ci.fields.extend(own)
        for i in range(len(ci.fields)):
            ci.fpos[ci.fields[i]] = i
        for f in b.fflag:
            ci.fflag[f] = b.fflag[f]
        for f in extra:
            ci.fextra[f] = True
        for f in b.fbox:
            ci.fbox[f] = b.fbox[f]
        for f in b.fields:
            if f not in b.fflag:
                fl.sup.append(f)
        fl.leak = b.leak
        fl.base = shown(ci.base)
        nb = len(ci.fields) - len(own)
    for f in ci.fields:
        if f.startswith(" "):
            fl.defd["." + f] = True
    fl.fields = ci.fields
    if ci.exc != "" and ("__init__" not in ci.methods or ci.methods["__init__"].cls != ci.name):
        # its constructor calls the __init__ of its base (or of none)
        for f in fl.sup:
            fl.put("." + f)
        fl.exposed()
        ci.leak = fl.leak
    elif ci.methods["__init__"].node.kids[0].kind == "noann":
        if not self.is_dc(ci.name) or "no-init" in ci.dcopts:
            fl.exposed()
        for f in ci.fields:
            if f in ci.fopts and "no-init" in ci.fopts[f] and f not in ci.fdefault and f not in ci.factory:
                fl.unsafe[f] = True  # (a field(init=False) without a default, which the __init__ @dataclass writes leaves unassigned)
    else:
        init = ci.methods["__init__"]
        asg: dict[str, bool] = {}
        collect(init.node.kids[2].kids, asg)
        if init.params[0] not in asg:
            # (if __init__ rebinds self, no assignment is known to reach the new object)
            fl.me = init.params[0]
            fl.sbase = self.classes[init.cls].base if init.cls in self.classes else ""
            # (outside a hierarchy, whose reads keep their flags' tests; the builtin hasattr)
            fl.probes = ci.exc == "" and ci.tag == 0 and "hasattr" not in asg and "hasattr" not in init.params and not self.bound("hasattr")
            self.fl_stmts(fl, init.node.kids[2].kids)
        fl.exposed()
        ci.leak = fl.escaped
    for f in ci.fields:
        # A derived constructor can omit the base constructor, or call an override before
        # assigning its own fields. Keep assignment bits in the root layout so base-typed
        # reads remain safe for every ordinary subclass, including future call paths.
        checked = (ci.tag > 0 and not f.startswith(" ")) or f in ci.fextra
        if (checked or f in fl.unsafe or f in fl.probed or ci.name + "." + f in self.cvars) and f not in ci.fflag:
            if ci.fpos[f] < nb and f in fl.unsafe:
                # (the base's code, which reads it with no flag to test)
                self.line = ci.node.line
                self.err(f"{short(ci.name)}.__init__ may leave field '{f}' of {short(ci.base)} unassigned where it is read: assign it, or call super().__init__(...) first")
            ci.fflag[f] = len(ci.fields) + ci.nflag
            ci.nflag += 1
            if not checked and f not in fl.unsafe and ci.name + "." + f not in self.cvars:
                ci.fsure[f] = True  # (only hasattr tests its flag: no read finds it unassigned)
    # Identity boxes follow flags so subclasses can embed this complete prefix. A
    # provisional None field reserves a slot: later inference can make it numeric.
    if dynamic_program():
        for f in ci.fields:
            if not f.startswith(" ") and f not in ci.fbox and (numeric_identity(ci.ftypes[f]) or ci.ftypes[f] == NONEVAR):
                ci.fbox[f] = len(ci.fields) + ci.nflag + ci.nbox
                ci.nbox += 1

def gen_default_home(self, ci: ClassInfo, fl: str) -> ClassInfo:
    # the class whose class body binds class attribute fl of ci: ci's, or the base's that an
    # exception class inherits it from (the same default, which declare_fields copies down;
    # a class body that binds fl again has a default of its own)
    while fl in ci.fdefault and ci.base in self.classes and fl in self.classes[ci.base].fdefault and self.classes[ci.base].fdefault[fl] is ci.fdefault[fl]:
        ci = self.classes[ci.base]
    return ci

def gen_fl_defaults(self, n: Node) -> list[Node]:
    # the default values a def or class statement evaluates (see hoist)
    out: list[Node] = []
    fs: list[FnInfo] = []
    if n.kind == "defaults":
        fs.append(self.funcs[n.s])
    else:
        ci = self.classes[n.s]
        for fl in ci.fields:
            if fl in ci.fdefault and not is_const(ci.fdefault[fl]) and self.default_home(ci, fl) is ci:
                out.append(ci.fdefault[fl])
        for f in ci.methods.values():
            if f.cls == ci.name:
                fs.append(f)
    for f in fs:
        for d in f.defaults:
            if not is_const(d):
                out.append(d)
    return out

def gen_scc(self, root: str, num: dict[str, int], low: dict[str, int], stack: list[str]) -> None:
    # Tarjan's algorithm over the import graph (deps) from module root: the modules numbered
    # and not yet in a component are on the stack. The search keeps its path in lists, since
    # a chain of imports can be longer than CPython's recursion limit
    path: list[str] = []
    outs: list[list[str]] = []
    nxt: list[int] = []
    x = root
    enter = True
    while True:
        if enter:
            # enter module x
            num[x] = len(num)
            low[x] = num[x]
            stack.append(x)
            path.append(x)
            outs.append(self.deps.get(x, "").split())
            nxt.append(0)
            enter = False
        a = path[-1]
        if nxt[-1] < len(outs[-1]):
            x = outs[-1][nxt[-1]]
            nxt[-1] += 1
            if x not in num:
                enter = True
            elif x not in self.comp:
                low[a] = min(low[a], num[x])
            continue
        # leave module a
        path.pop()
        outs.pop()
        nxt.pop()
        if low[a] == num[a]:
            while True:
                y = stack.pop()
                self.comp[y] = a
                if y == a:
                    break
        if len(path) == 0:
            return
        low[path[-1]] = min(low[path[-1]], low[a])

def gen_user_call(self, n: Node) -> bool:
    # may running n call a user function, method or constructor? (an import of a user module
    # runs the module's code; a def, its decorators; a function read as a value, or a lambda,
    # may be called through what holds it, fs[0]() or sorted(xs, key=f), but name = f only
    # makes name one too: fvars)
    if n.kind == "def" and self.applies(n, False, {}):
        return True
    if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.funcs or n.kids[0].s in self.classes):
        return True
    if n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[1].kind == "name" and (n.kids[1].s in self.funcs or n.kids[1].s in self.fvars):
        self.fvars[n.kids[0].s] = True
        return False
    if n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[1].kind == "lambda":
        self.fvars[n.kids[0].s] = True  # (name = lambda ...: as name = f, but its defaults run here)
        for pa in n.kids[1].kids[0].kids:
            if self.user_call(pa.kids[1]):
                return True
        return False
    if n.kind == "lambda":
        return True  # (a function made here, which what it is given to may call)
    if n.kind == "pass":
        return False  # (also an alias, name = f, that the loader resolved: its kids are left)
    if n.kind == "name" and (n.s in self.funcs or n.s in self.fvars):
        return True
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s in self.classes:
        return True  # C.m(...): a static or class method
    if n.kind == "raise":
        for x in n.kids:
            if x.kind == "name" and x.s in self.classes:
                return True  # raise E (or from E): the class is called, which runs its __init__
    if n.kind == "uimport":
        # it runs a module's code, which can call this module's functions only if it imports
        # this module (circular imports): as this module imports it, only if both are in one
        # strongly connected component of the import graph. A package's own name, before its
        # submodule's, runs nothing
        for x in n.kids:
            if x.s != self.flowmod and self.comp[x.s] == self.comp[self.flowmod]:
                return True
        return False
    if n.kind == "defaults" or n.kind == "cdefaults":
        for d in self.fl_defaults(n):
            # (a function or lambda given as a default runs only when the function does)
            if d.kind != "lambda" and not (d.kind == "name" and d.s in self.funcs) and self.user_call(d):
                return True
    for k in n.kids:
        if self.user_call(k):
            return True
    return False

def gen_fl_stmts(self, fl: Flow, body: list[Node]) -> None:
    for st in body:
        self.fl_stmt(fl, st)

def gen_fl_stmt(self, fl: Flow, n: Node) -> None:
    k = n.kind
    if k == "assign":
        self.fl_expr(fl, n.kids[-1])
        for i in range(len(n.kids) - 1):
            self.fl_target(fl, n.kids[i])
    elif k == "annassign":
        if len(n.kids) == 3:
            self.fl_expr(fl, n.kids[2])
            self.fl_target(fl, n.kids[0])
    elif k == "augassign":
        self.fl_expr(fl, n.kids[0])
        self.fl_expr(fl, n.kids[1])
        self.fl_target(fl, n.kids[0])
    elif k == "if":
        self.fl_expr(fl, n.kids[0])
        neg = n.kids[0].kind == "unary" and n.kids[0].s == "not"
        f = fl.probe(n.kids[0].kids[0] if neg else n.kids[0])  # (the branch where hasattr(self, "f") is true has f)
        mark = len(fl.log)
        if f != "" and not neg:
            fl.put("." + f)
        self.fl_stmts(fl, n.kids[1].kids)
        then = fl.since(mark)
        fl.undo(mark)
        if f != "" and neg:
            fl.put("." + f)
        self.fl_stmts(fl, n.kids[2].kids)
        fl.join(then, mark)
    elif k == "while" or k == "for":
        self.fl_expr(fl, n.kids[0] if k == "while" else n.kids[1])
        dels: dict[str, bool] = {}
        deleted(n.kids[2 if k == "for" else 1].kids, dels)
        for nm in dels:
            fl.drop(nm)  # (a del in the body may run before a read in the next pass)
        mark = len(fl.log)
        btrue = fl.btrue
        bjoin = fl.bjoin
        bany = fl.bany
        bwas = fl.bwas
        bnew = fl.bnew
        unb = fl.unb
        fl.btrue = k == "while" and n.kids[0].kind == "True"
        fl.bjoin = {}
        fl.bany = False
        fl.bwas = {}
        fl.bnew = {}
        fl.unb = []
        if k == "for":
            self.fl_target(fl, n.kids[0])
        self.fl_stmts(fl, n.kids[2 if k == "for" else 1].kids)
        exits = fl.bjoin
        broke = fl.bany
        # (undone before the enclosing loop's fields are back: to that loop, the body changed nothing)
        fl.undo(mark)
        fl.btrue = btrue
        fl.bjoin = bjoin
        fl.bany = bany
        fl.bwas = bwas
        fl.bnew = bnew
        fl.unb = unb
        if n.kids[-1].s == "else":
            # (after the loop only what was assigned before it is surely assigned, less what
            # the else block unbinds: the loop is left at its end or, from a break, in a state
            # that has what was assigned before it. A while True never runs its else block)
            self.fl_stmts(fl, n.kids[-1].kids)
            if k == "while" and n.kids[0].kind == "True":
                fl.undo(mark)
            else:
                st = fl.since(mark)
                fl.undo(mark)
                fl.join(st, mark)
        if k == "while" and n.kids[0].kind == "True":
            # while True is left only through break: in what the states at its breaks have
            # in common
            if not broke:
                fl.put(" dead")
            for x in exits:
                if exits[x]:
                    fl.put(x)
                else:
                    fl.drop(x)
    elif k == "break":
        for nm in fl.unb:
            fl.drop(nm)
        if fl.btrue and " dead" not in fl.defd:
            fl.fold()
        fl.put(" dead")
    elif k == "continue" or k == "return" or k == "raise":
        for c in n.kids:
            self.fl_expr(fl, c)
        if k == "return":
            fl.exposed()
        fl.put(" dead")
    elif k == "defaults" or k == "cdefaults":
        for d in self.fl_defaults(n):
            self.fl_expr(fl, d)
        fl.put(n.s)
    elif k == "def":
        self.fl_nested(fl, n)  # (a def in a function)
    elif k == "lclass":
        self.fl_expr(fl, self.cnodes[n.line])  # (the reads of a class Pystachy leaves out, also in its methods)
    elif k == "expr" or k == "assert" or k == "del":
        for c in n.kids:
            mark = len(fl.log)
            self.fl_expr(fl, c)
            if k == "del" and c.kind == "name":
                fl.drop(c.s)  # unbound from here on
            if k == "assert" and c is not n.kids[0]:
                fl.undo(mark)  # (the message runs only where the assertion fails: its := bind nothing after it)
    elif k == "with":
        # (in a program with a context manager of its own, whose __exit__ may suppress the
        # exception, the block may end anywhere, and the statement goes on: as a try statement
        # whose except clause passes; not where each item is a call of the builtin open(),
        # whose file suppresses nothing)
        mark = len(fl.log)
        files = True
        for it in n.kids[:-1]:
            self.fl_expr(fl, it.kids[0])
            if len(it.kids) == 2:
                self.fl_target(fl, it.kids[1])
            if not self.open_call(it.kids[0]) or "open" in fl.scope:
                files = False
        self.fl_stmts(fl, n.kids[-1].kids)
        if not files and self.cm_exits():
            st = fl.since(mark)
            fl.undo(mark)
            bdels: dict[str, bool] = {}
            deleted(n.kids[-1].kids, bdels)
            for nm in bdels:
                fl.drop(nm)
            fl.join(st, mark)
    elif k == "try":
        # an except clause starts from the state before the statement less what the body may
        # have unbound, the else block goes on from the body, and the statement ends in the
        # join of those that end, then the finally block. A copy of that runs as an exception,
        # a break or a return leaves too: it is looked at once more, from the state before the
        # statement less everything the statement may unbind (which a break that runs it may
        # have left too, so what it unbinds is unbound from the start)
        orelse: list[Node] = []
        fin: list[Node] = []
        hasfin = False
        for b in n.kids[1:]:
            if b.kind == "block" and b.s == "else":
                orelse = b.kids
            elif b.kind == "block":
                fin = b.kids
                hasfin = True
        fdels: dict[str, bool] = {}
        deleted(fin, fdels)
        for nm in fdels:
            fl.drop(nm)
            fl.unb.append(nm)  # (a break out of the statement runs the finally block first)
        mark = len(fl.log)
        bdels = {}
        deleted(n.kids[0].kids, bdels)
        self.fl_stmts(fl, n.kids[0].kids)
        self.fl_stmts(fl, orelse)
        for h in n.kids[1:]:
            if h.kind != "except":
                continue
            st = fl.since(mark)
            fl.undo(mark)
            for nm in bdels:
                fl.drop(nm)
            self.fl_expr(fl, h.kids[0])  # (its classes are read when an exception gets to it)
            if h.s != "":
                fl.put(h.s)
                fl.unb.append(h.s)
            self.fl_stmts(fl, h.kids[1].kids)
            if h.s != "":
                fl.unb.pop()
                fl.drop(h.s)
            fl.join(st, mark)
        for nm in fdels:
            fl.unb.pop()
        if hasfin:
            st = fl.since(mark)
            fl.undo(mark)
            dels = {}
            deleted([n], dels)
            for nm in dels:
                fl.drop(nm)
            self.fl_stmts(fl, fin)
            fl.undo(mark)
            for nm in st:
                if st[nm]:
                    fl.put(nm)
                else:
                    fl.drop(nm)
            self.fl_stmts(fl, fin)

def gen_fl_target(self, fl: Flow, t: Node) -> None:
    if t.kind == "name":
        fl.put(t.s)
    elif t.kind == "attr" and fl.me != "" and t.kids[0].kind == "name" and t.kids[0].s == fl.me and t.s not in fl.fields:
        fl.exposed()  # (self.x = v of a property x: its setter takes self)
        fl.escaped = True
    elif t.kind == "attr" and fl.me != "" and t.kids[0].kind == "name" and t.kids[0].s == fl.me:
        fl.put("." + t.s)
    elif t.kind == "tuple" or t.kind == "starred":
        for k in t.kids:
            self.fl_target(fl, k)
    else:
        for k in t.kids:
            self.fl_expr(fl, k)

def gen_fl_expr(self, fl: Flow, e: Node) -> None:
    k = e.kind
    if k == "lambda":
        self.fl_nested(fl, e)
        return
    if k == "name":
        if e.s in fl.tracked and e.s not in fl.defd and " dead" not in fl.defd:
            e.chk = True
            fl.marks[e.s] = True
        if e.s == fl.me:
            fl.exposed()
            fl.escaped = True
    elif k == "attr" and fl.me != "" and e.kids[0].kind == "name" and e.kids[0].s == fl.me:
        if e.s not in fl.fields:
            fl.exposed()  # (self.m, a method bound to self: what it is given to may call it)
            fl.escaped = True
        elif "." + e.s not in fl.defd and " dead" not in fl.defd:
            fl.unsafe[e.s] = True
    elif k == "listcomp":
        # [elt for target in iter if cond]: iter is read outside, the rest with target bound;
        # a later for clause reads its iterable, then binds its target (what a := there binds is
        # not surely bound after it)
        self.fl_expr(fl, e.kids[2])
        mark = len(fl.log)
        self.fl_target(fl, e.kids[1])
        for c in e.kids[3:]:
            if c.kind == "compfor":
                self.fl_expr(fl, c.kids[1])
                self.fl_target(fl, c.kids[0])
            else:
                self.fl_expr(fl, c)
        self.fl_expr(fl, e.kids[0])
        fl.undo(mark)
    elif k == "walrus":
        self.fl_expr(fl, e.kids[0])
        fl.put(e.s)
    elif k == "boolop" or k == "ifexp" or k == "cmp":
        # what may not run: the operands of and/or after the first, the arms of an if-else and
        # the comparisons of a chain after the first. What a := there binds is not surely bound
        # after it (each arm is analysed from the state after the test, and they are joined).
        # Defaults of lambdas evaluated in an operand can bind names too; their bodies cannot.
        n = 1 if k != "cmp" else 2
        for c in e.kids[:n]:
            self.fl_expr(fl, c)
        mark = len(fl.log)
        if k == "ifexp":
            self.fl_expr(fl, e.kids[1])
            then = fl.since(mark)
            fl.undo(mark)
            self.fl_expr(fl, e.kids[2])
            fl.join(then, mark)
        else:
            for c in e.kids[n:]:
                self.fl_expr(fl, c)
            fl.undo(mark)
    elif fl.probe(e) != "":
        # (hasattr(self, "f") reads f's flag and lets self escape no further)
        if "." + e.kids[2].s not in fl.defd and " dead" not in fl.defd:
            fl.probed[e.kids[2].s] = True
    elif k == "call":
        c = e.kids[0]
        # super().__init__(...) in an exception class's __init__ (fl_fields), or Base.__init__(self, ...)
        sup = fl.me != "" and c.kind == "attr" and c.s == "__init__" and c.kids[0].kind == "call" and c.kids[0].kids[0].kind == "name" and c.kids[0].kids[0].s == "super"
        if sup:
            for a in c.kids[0].kids[1:]:
                self.fl_expr(fl, a)
        elif fl.me != "" and c.kind == "attr" and c.kids[0].kind == "call" and len(c.kids[0].kids) == 1 and c.kids[0].kids[0].kind == "name" and c.kids[0].kids[0].s == "super" and "super" not in self.funcs and self.fl_super(fl, c.s):
            pass  # (super().m(...), which reads only the fields fl_super marks)
        elif c.kind == "attr":
            self.fl_expr(fl, c.kids[0])
        elif fl.me != "" and c.kind == "name" and c.s == "super" and c.s not in self.funcs:
            # super() otherwise (super().m(...)): self, which the base's methods are given, as self.m(...)
            fl.exposed()
            fl.escaped = True
        elif c.kind != "name" or (c.s not in self.funcs and c.s not in self.classes) or c.s == fl.me:
            self.fl_expr(fl, c)  # (o(args) reads variable o, whose object is called; self shadows a function or class)
        elif c.s in fl.tracked and c.s not in fl.defd and " dead" not in fl.defd:
            c.chk = True
            fl.marks[c.s] = True
        based = fl.me != "" and c.kind == "attr" and c.s == "__init__" and c.kids[0].kind == "name" and c.kids[0].s == fl.base and len(e.kids) > 1 and e.kids[1].kind == "name" and e.kids[1].s == fl.me
        for i in range(2 if based else 1, len(e.kids)):
            self.fl_expr(fl, e.kids[i])
        if sup or based:
            for f in fl.sup:
                fl.put("." + f)
            if fl.leak:
                fl.exposed()
    else:
        for c in e.kids:
            self.fl_expr(fl, c)

# ---- statements
