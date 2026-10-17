"""Loader component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
from src.pystachy_compiler.analysis import (
    accel_try,
    binds,
    binds_first,
    bound_in,
    builtin_has,
    builtin_import,
    builtin_module,
    builtin_of,
    calls,
    catches_import,
    clean_doc,
    collect,
    del_line,
    declares,
    deferred_use,
    deleted,
    false_flag,
    sole_binding,
    first_use,
    fn_globals,
    global_assigns,
    globals_in,
    has_all,
    import_error,
    import_reads,
    imports_user,
    is_main_guard,
    local_names,
    local_types,
    mark,
    may_end,
    module_reads,
    names_name,
    own_specials,
    range_values,
    read_names,
    rebound,
    refers,
    scope_globals,
    scope_names,
    special_import,
    specials,
    surely_binds,
    top_bindings,
    walrus_names,
)
from src.pystachy_compiler.diagnostics import FILES, LINES, MODDUNDERS, RAW, fail
from src.pystachy_compiler.lexer import KEYWORDS, Lexer
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.specs import (
    ABCS,
    ABSTRACT_DECOS,
    ANNKINDS,
    CBUILTIN,
    CTYPES,
    GENERICS,
    GLUE,
    ITERS,
    MODNAMES,
    MODULES,
    NOCALL,
    IMPLEMENTATION,
    OSCONST,
    PLATFORM,
    PYBUILTINS,
    RANGES,
    STANDINS,
    TYPESMOD,
    IOMOD,
    TYPING,
    VERSIONINFO,
    is_excname,
)
from src.pystachy_compiler.syntax import Node, comp_names, has_kind, mk, names_in
from src.pystachy_compiler.utils import clone, int_fits, is_const



def cm_names(body: Node) -> list[str]:
    # the names module body imports contextlib's contextmanager as (contextmanager,
    # contextlib.contextmanager, or another as)
    out: list[str] = []
    for st in body.kids:
        for a in st.kids if st.kind == "import" else []:
            if a.kind == "alias" and len(a.kids) == 2 and a.kids[0].s == "contextlib.contextmanager" and st.s == "from":
                out.append(a.s)
            elif a.kind == "alias" and len(a.kids) == 2 and a.kids[0].s == "contextlib" and st.s != "from":
                out.append(a.s + ".contextmanager")
    return out


def cm_root(c: str, name: str, bases: dict[str, list[str]], cms: list[str]) -> str:
    # the first class from c up its bases (classes of the module, by name) that defines the
    # @contextmanager method name, the furthest up it; "" when none does
    for b in bases.get(c, []):
        r = cm_root(b, name, bases, cms)
        if r != "":
            return r
    return c if c + "." + name in cms else ""


def cm_methods(n: Node, names: list[str]) -> None:
    # a method decorated @contextmanager (names: as the module imports it) is the generator method
    # _pys_cm_NAME, and NAME(self, /, *args, **kwds) returns the manager that
    # contextmanager(self._pys_cm_NAME)(*args, **kwds) makes: what CPython's helper does, bound to
    # the object (the subset has no decorated methods). Its generator is C's own: in a class C
    # that derives from a class of the module or that one derives from, C._pys_cm_NAME(self,
    # *args, **kwds) (super().NAME() runs the base class's), else self._pys_cm_NAME(...); and the
    # function it keeps (for a decorator's calls, which make the generator again) is bound to self
    # taken as an object of the class that first defines NAME so, so that NAME returns one type
    # whatever subclass self is. A generic class keeps contextmanager(self._pys_cm_NAME) (C alone
    # names no type there)
    bases: dict[str, list[str]] = {}
    for st in n.kids:
        if st.kind == "subclass":
            bases[st.s] = [x.s for x in st.kids[1:] if x.kind == "name"]
        elif st.kind == "class":
            bases[st.s] = []
    derived: dict[str, bool] = {}
    for c in bases:
        for x in bases[c]:
            if x in bases:
                derived[c] = True
                derived[x] = True
    cms: list[str] = []
    top: list[Node] = []
    imported = False
    for st in n.kids:
        if st.kind == "class" or st.kind == "subclass":
            b = st.kids[0] if st.kind == "class" else st.kids[0].kids[0]
            generic = st.kind == "subclass" and len([x for x in st.kids[1:] if x.kind == "typeparams"]) > 0
            kept: list[Node] = []
            for d in b.kids:
                if d.kind == "def" and len(d.kids) == 4 and d.kids[3].kind == "deco" and len(d.kids[3].kids) == 0 and d.kids[3].s in names and len(d.kids[0].kids) > 0 and d.kids[0].kids[0].kind == "param":
                    me = d.kids[0].kids[0].s
                    cms.append(st.s + "." + d.s)
                    if generic:
                        src = f"def {d.s}({me}, /, *args, **kwds):\n    return {d.kids[3].s}({me}._pys_cm_{d.s})(*args, **kwds)\n"
                    else:
                        if not imported:
                            top.append(Parser(Lexer("from contextlib import _GeneratorContextManager as _pys_cm_GCM\n", st.line).file()).module().kids[0])
                            imported = True
                        own = f"{st.s}._pys_cm_{d.s}({me}, *args, **kwds)" if st.s in derived else f"{me}._pys_cm_{d.s}(*args, **kwds)"
                        src = f"def {d.s}({me}, /, *args, **kwds):\n    _pys_cm_self: {cm_root(st.s, d.s, bases, cms)} = {me}\n    return _pys_cm_GCM(_pys_cm_self._pys_cm_{d.s}, args, kwds, {own})\n"
                    w = Parser(Lexer(src, d.line).file()).module().kids[0]
                    d.s = "_pys_cm_" + d.s
                    d.kids = d.kids[:3]
                    kept.append(d)
                    kept.append(w)
                else:
                    kept.append(d)
            b.kids = kept
        top.append(st)
    n.kids = top


def tb_import(n: Node) -> None:
    # from types import TracebackType (an __exit__'s annotation) imports lib/_pystachy_types.py's
    # TracebackType, which lib/types.py binds too, without the rest of lib/types.py
    for st in n.kids:
        if st.kind == "import" and st.s == "from" and len(st.kids) > 0 and len([a for a in st.kids if a.kind != "alias" or len(a.kids) != 2 or a.kids[0].s != "types.TracebackType" or a.kids[1].s != "types"]) == 0:
            for a in st.kids:
                a.kids[0].s = "_pystachy_types.TracebackType"
                a.kids[1].s = "_pystachy_types"
        elif st.kind != "def" and st.kind != "class" and st.kind != "subclass":
            tb_import(st)

def ascii_ident(s: str) -> bool:
    # is ASCII string s an identifier, as str.isidentifier() tells
    for i in range(len(s)):
        c = s[i]
        if not (c == "_" or ("a" <= c and c <= "z") or ("A" <= c and c <= "Z") or (i > 0 and "0" <= c and c <= "9")):
            return False
    return s != ""


class Loader:
    def __init__(self, dirs: list[str]):
        self.dirs = dirs  # the module search path
        self.ext = ""  # pystachy ext: the main program is the extension module of this name (its __name__)
        self.rtmode = False  # runtime.py's module imports are declarations; no module code runs
        self.mods: dict[str, Mod] = {}
        self.order: list[Mod] = []  # every module after those its top-level code imports
        # imports in the functions of imported modules, resolved once all module-level imports
        # are loaded: the function may never be compiled, as CPython may never run it
        self.later: list[Node] = []
        self.laterm: list[Mod] = []
        self.laterb: list[Node] = []
        self.laterd: list[str] = []
        self.latert: list[int] = []  # (the try statements each is in: intry)
        # what the imports in a function bind (for that function only), by the def's line
        self.fks: dict[str, dict[str, str]] = {}
        self.fkline: dict[str, int] = {}  # and the line of the first import that binds each name, by "<def's line> <name>"
        self.fgl: dict[str, dict[str, bool]] = {}  # and the names its global statements declare
        self.curdef = ""  # the def whose body imports() is in
        self.fk: dict[str, str] = {}  # visible function import bindings, including enclosing functions'
        self.fkey = ""  # and its def's line
        self.fkowner: dict[str, str] = {}  # the def whose import binds each visible name (closures inherit them)
        # The try statements imports() is in; module import bindings and function imports in try
        # statements ("<module> <def line, or empty> <name>"), each with its flag (import_binds(),
        # checked by Node.mchk); and the names function imports outside try statements bind
        self.intry = 0
        self.optry = False  # (in the body of one whose clauses may catch ImportError: not an optional import)
        self.fragile: dict[str, str] = {}
        self.solid: dict[str, bool] = {}
        # the submodules that imports in try statements run, which their package has as an attribute
        # only once an import of them has run to its end (Gen.modchk), and the reads through such an
        # attribute that qmod() found in the expression being qualified (Node.mchk)
        self.trysubs: dict[str, bool] = {}
        self.subchk: list[str] = []
        self.parsed: dict[str, Node] = {}  # each module file, parsed once
        # and what its code binds, surely and maybe, as scan() finds it before it is loaded
        self.rawbound: dict[str, dict[str, bool]] = {}
        # and those of the code of the module whose code is being simplified, up to statement ownpos
        self.ownkids: list[Node] = []
        self.ownpos = 0
        self.ownsure: dict[str, bool] = {}
        self.ownmaybe: dict[str, bool] = {}
        self.rawsure: dict[str, dict[str, bool]] = {}
        self.failc: dict[str, str] = {}  # what init_fails() found for a module not loaded yet
        self.scanning: dict[str, bool] = {}  # the modules init_fails() is looking at
        # the index of the top-level statement whose code simplify() or init_raise() is in, -1 in a
        # function, and whether simplify() is in a class body there
        self.pos = -1
        self.incls = False
        # the names that the top-level code imports() is in has surely bound by then, and those it
        # may have bound (for take())
        self.sure: dict[str, bool] = {}
        self.maybe: dict[str, bool] = {}
        # each optional import that optional() decided: s is the module whose import fails, if its
        # code raises ImportError, and the kids are the other modules whose code runs in the try;
        # with the module it is in, and the other statements that run in the try (checked by guarded())
        self.sites: list[Node] = []
        self.sitem: list[Mod] = []
        self.siterest: list[Node] = []
        # what raises() found for a module, where that does not depend on the modules whose code was
        # running (rcyc: a result that did); the function fn_raises() found, "?" before it looks
        self.rmemo: dict[str, int] = {}
        self.rcyc = False
        self.fn = "?"
        # each from-import of a name a package binds itself (take()), with the bindings it went to,
        # for submodules(): s is the name bound, the kids the package, the name and the copy if any
        self.taken: list[Node] = []
        self.takek: list[dict[str, str]] = []
        # each from-import of a variable (take()), with the bindings it went to, for late_takes(): s
        # is the name bound, the kids the module, the name, the copy, what bound the name before (but
        # another from-import of a variable), where ("@" and the module, or the function) and the line
        # its module's code was at (Mod.at, 0 once done); vtook: names only such imports bound so far
        self.vtaken: list[Node] = []
        self.vtakek: list[dict[str, str]] = []
        self.vtook: dict[str, bool] = {}
        self.aliased: dict[str, Node] = {}  # the alias statements late_aliases() made, by "<module> <name>"
        # each star import of a package without __all__, with the module it is in (submodules())
        self.stars: list[Node] = []
        self.starm: list[Mod] = []
        self.qdef = False  # is qstmts() in a function
        # the type parameters of the generic classes and defs (class C[T], def f[T]) it is in, by
        # name: the names of their own that they are qualified to (<class's or def's name>$$T,
        # unlike any other)
        self.qren: dict[str, str] = {}
        # the function simplify() is in (own_specials()), and the names that its own imports which
        # special_import() recognizes have surely bound where simplify() is
        self.fs = Mod("", "", "")
        self.fsure: dict[str, bool] = {}
        self.unsure: dict[str, dict[str, bool]] = {}  # what each def reads before an import of it surely ran (import_reads())
        self.lazyann = False  # the module deftime() walks imports annotations from __future__
        self.tpnames: dict[str, bool] = {}  # the type parameters (def f[T], class C[T]) around what it reads
        self.called = 0  # and its code may have called a function by now (1), or imported a module (2)
        self.dm = Mod("", "", "")  # (that module)
        self.bdecos: dict[int, bool] = {}  # the decorators, by line, that surely name a builtin
        # the names of dm's code that deftime() has seen bound to a class without bases, decorators
        # or __class_getitem__ (a type, which CPython cannot subscript) and not bound again since
        self.known: dict[str, bool] = {}
        # the module-level statements name.__doc__ = ... that simplify() dropped, each a "docset"
        # node, with its module
        self.docsets: list[Node] = []
        self.docsetm: list[Mod] = []

    def program(self, path: str, src: str) -> list[Mod]:
        # the main program and the modules it imports, in the order their code may first run
        m = Mod("", path, "")
        FILES.append(path)
        m.body = Parser(Lexer(src, 1).file()).module()
        tb_import(m.body)
        cm_methods(m.body, cm_names(m.body))
        self.prescan(m)
        self.simplify(m, m.body, {})
        self.docstring(m)
        self.bindings(m)
        self.sure = m.sure
        self.maybe = m.maybe
        self.imports(m, m.body, False)
        self.namedtuples(m)
        self.order.append(m)
        for i in range(len(self.later)):
            st = self.later[i]
            self.curdef = self.laterd[i]
            self.intry = self.latert[i]
            out: list[Node] = []
            if self.loaded(self.laterm[i], st):
                self.import_stmt(self.laterm[i], st, True, out)
            else:
                for a in st.kids:
                    p = a.kids[1].s if not st.s.startswith("from.") else self.relative(self.laterm[i], st.s, a.kids[1].s, st.line)
                    msg = f"importing module '{p}' in a function of module '{self.laterm[i].name}' is not supported: the program's module-level code does not import it"
                    if p in self.mods and st.s.startswith("from"):
                        xn = a.kids[0].s[a.kids[0].s.rfind(".") + 1 :]
                        msg = f"cannot import name '{xn}' from '{p}'"
                    out.append(mk("badimport", msg, st.line, []))
                    self.bind(self.laterm[i], a.s, "x:" + msg, True, st.line)
            b = self.laterb[i]
            for j in range(len(b.kids)):
                if b.kids[j] is st:
                    b.kids = b.kids[:j] + out + b.kids[j + 1 :]
                    break
        self.intry = 0
        if not self.rtmode and len(self.dirs) > 0 and RANGES not in self.mods and len([x for x in self.order if range_values(x.body, 0) and module_reads(x.body, "range")]) > 0:
            # range() as a value is an object of lib's class, whose module nothing imports: loaded
            # for a program that may use one (where a loop or a consumer takes the numbers at once,
            # the compiler steps through range(...) itself; the class's methods are compiled only
            # if the program calls them)
            self.load(RANGES, self.dirs[-1] + "/" + RANGES + ".py", "")
            self.order = [self.order[-1]] + self.order[:-1]
        if not self.rtmode and len(self.dirs) > 0 and ITERS not in self.mods and len([x for x in self.order if module_reads(x.body, "iter")]) > 0:
            # iter() makes iterator objects of builtin containers: of lib's classes, whose module
            # nothing imports (it imports nothing either, so it comes first)
            self.load(ITERS, self.dirs[-1] + "/" + ITERS + ".py", "")
            self.order = [self.order[-1]] + self.order[:-1]
        self.guarded()
        self.submodules()
        more = True
        while more:
            # (until no from-import of an alias is left to make one: an alias may be of one)
            for x in self.order:
                self.late_aliases(x)
            more = self.late_takes(False)
        self.late_takes(True)
        self.doccycles()
        for x in self.order:
            self.lazyann = False
            self.called = 0
            self.dm = x
            self.known = {}
            env: list[dict[str, bool]] = [{}, {}, {}, {}]  # (a package binds __path__, annotations __annotations__)
            mark((["__path__"] if x.pdir != "" else []) + (["__annotations__"] if has_kind(x.body, "annassign") else []), env[0], env[1], [])
            self.deftime(x, x.body.kids, env, "", [], True)
        for i in range(len(self.docsets)):
            k = self.docsetm[i].kinds.get(self.docsets[i].s, "")
            if k.startswith("m:"):
                fail(f"assigning the __doc__ of module '{k[2:]}' is not supported", self.docsets[i].line)
        for x in self.order:
            self.singletons(x)
            self.qstmts(x, x.body.kids, {}, False)
        return self.order

    def singletons(self, m: Mod) -> None:
        # class C: ... directly followed by C = C() at module level (a singleton, as enum's
        # _not_given): from then on C is a variable, the instance (its kind), and the class, which
        # only that call names, is C-0, which keeps C's name (__name__, __qualname__, type(C): a
        # specialization's name is its class's so, short()). Its call runs none of the program's
        # code (no bases but object, which deftime() has dropped, decorators, __init__ or __new__),
        # which could read C still unbound
        b = m.body.kids
        for i in range(len(b) - 1):
            c = b[i]
            a = b[i + 1]
            if c.kind == "class" and len(c.kids) == 1 and a.kind == "assign" and len(a.kids) == 2 and a.kids[0].kind == "name" and a.kids[0].s == c.s and a.kids[1].kind == "call" and len(a.kids[1].kids) == 1 and a.kids[1].kids[0].kind == "name" and a.kids[1].kids[0].s == c.s:
                own = top_bindings(c.kids[0].kids)
                if "__init__" not in own and "__new__" not in own:
                    c.s = m.q + c.s + "-0"  # (qualified: qname() keeps it)
                    a.kids[1].kids[0].s = c.s

    def docstring(self, m: Mod) -> None:
        # m's __doc__ (Mod.doc): its docstring, a string literal alone in its first statement, as
        # CPython 3.13's compiler cleans it; else None. Where m's code binds __doc__ itself (what
        # simplify() left of it), it is a variable, which CPython's code assigns the docstring (or
        # None) before its first statement. So does a statement put after the docstring and the
        # from __future__ imports here, unless the first statement that names __doc__ binds it
        # before a user import can expose this module (and its value does not read it).
        # With a docstring, __doc__ = <docstring>; without one,
        # __doc__: str | None = None, where that statement is no def or class (one of whose
        # functions reads it: such a read before m's code binds it raises NameError)
        b = m.body
        if b.s == "doc" and b.kids[0].kind == "expr" and b.kids[0].kids[0].kind == "str":
            m.doc = mk("str", clean_doc(b.kids[0].kids[0].s), b.kids[0].line, [])
        if "__doc__" not in rebound(b.kids, True):
            return
        at = del_line(b, "__doc__", False)
        if at > 0:
            fail("deleting the module's __doc__ is not supported (CPython's code then reads builtins.__doc__)", at)
        i = 1 if b.s == "doc" else 0
        while i < len(b.kids) and b.kids[i].kind == "import" and b.kids[i].s == "from" and b.kids[i].kids[0].kids[1].s == "__future__":
            i += 1
        j = i
        while j < len(b.kids) and (not names_name(b.kids[j], "__doc__") or (b.kids[j].kind == "annassign" and len(b.kids[j].kids) == 2)):
            j += 1  # (__doc__: str neither binds nor reads it)
        if j == len(b.kids):
            return
        first = b.kids[j]
        direct = binds_first(first, "__doc__")
        exposed = imports_user(mk("block", "", first.line, b.kids[i : j + 1]))
        if (direct and not exposed) or (m.doc.kind != "str" and (first.kind == "def" or first.kind == "class" or first.kind == "subclass")):
            return
        line = b.kids[i].line
        v = mk(m.doc.kind, m.doc.s, line, [])
        ann = mk("name", "str", line, [])
        hasann = False
        for st in b.kids[i : j + 1]:
            if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s == "__doc__":
                ann = clone(st.kids[1])
                hasann = True
        if m.doc.kind == "str":
            b.kids.insert(i, mk("assign", "doccycle" if direct else "", line, [mk("name", "__doc__", line, []), v]))
        elif direct and first.kind == "assign" and not hasann:
            # Infer the optional type from its later value in the owning module's frame before
            # a circular importer compiles; no frontend type guess is needed.
            b.kids.insert(i, mk("assign", "doccycle", line, [mk("name", "__doc__", line, []), v]))
        else:
            t = mk("binop", "|", line, [ann, mk("None", "", line, [])])
            b.kids.insert(i, mk("annassign", "doccycle" if direct else "docinit", line, [mk("name", "__doc__", line, []), t, v]))

    def doccycles(self) -> None:
        # A direct rebinding needs the initial __doc__ only if a preceding import can observe
        # it through a cycle. Drop the provisional assignment otherwise, retaining support for
        # a different type after an unrelated import. The resolved imports are available now;
        # imports_mod also follows imported functions conservatively.
        for m in self.order:
            for i in range(len(m.body.kids)):
                st = m.body.kids[i]
                if (st.kind == "assign" or st.kind == "annassign") and st.s == "doccycle":
                    j = i + 1
                    while j < len(m.body.kids) and (not names_name(m.body.kids[j], "__doc__") or (m.body.kids[j].kind == "annassign" and len(m.body.kids[j].kids) == 2)):
                        j += 1
                    prefix = mk("block", "", st.line, m.body.kids[i + 1 : j + 1])
                    if not self.imports_mod(prefix, m.name, {}, True):
                        m.body.kids = m.body.kids[:i] + m.body.kids[i + 1 :]
                    elif m.doc.kind != "str":
                        # An annotation, with or without a value, describes the same storage as
                        # the implicit initial None; preserve its check on the later value.
                        for a in m.body.kids[i + 1 : j + 1]:
                            if a.kind == "annassign" and a.kids[0].kind == "name" and a.kids[0].s == "__doc__":
                                a.kids[1] = mk("binop", "|", a.line, [a.kids[1], mk("None", "", a.line, [])])
                        st.s = "docinit"
                    else:
                        st.s = ""
                    break

    def moddoc(self, n: Node, t: Mod) -> None:
        # n, a read of module t's __doc__ where t's code binds none, becomes that constant
        n.kind = t.doc.kind
        n.s = t.doc.s
        n.kids = []

    def loaded(self, m: Mod, st: Node) -> bool:
        # are the user modules import statement st names (and from-imported submodules) loaded
        for a in st.kids:
            p = a.kids[1].s
            if st.s.startswith("from."):
                p = self.relative(m, st.s, p, st.line)
            elif builtin_import(st, a) or p == "typing_extensions":
                continue
            elif builtin_module(p):
                p = a.kids[0].s  # (import collections.abc: the package collections)
            if p not in self.mods:
                return False
            if st.s.startswith("from") and a.s != "*":
                x = a.kids[0].s[a.kids[0].s.rfind(".") + 1 :]
                if x not in self.mods[p].kinds and p + "." + x not in self.mods and x != "__doc__":
                    return False
        return True

    def modpath(self, name: str) -> str:
        # the file module name is loaded from: NAME/__init__.py or NAME.py, the first found on the
        # module path or in the parent package, else the directories of a namespace package
        # (separated by ":"); "" if there is none
        if name in STANDINS and len(self.dirs) > 0:
            return self.dirs[-1] + "/" + STANDINS[name] + ".py"  # (lib's stand-in for a C module)
        if name in CBUILTIN:
            return ""  # a module built into CPython: no file on the path replaces it (find())
        if name == ITERS or name == RANGES:
            return ""  # (iter()'s classes and range's, which no program imports: see program)
        return self.filepath(name)

    def filepath(self, name: str) -> str:
        # modpath(), also of a module built into CPython
        dirs = self.dirs
        base = name
        dot = name.rfind(".")
        if dot >= 0:
            par = self.modpath(name[:dot])
            if par.endswith("/__init__.py"):
                dirs = [par[:-12]]
            elif par != "" and not par.endswith(".py"):
                dirs = par.split(":")
            else:
                return ""
            base = name[dot + 1 :]
        for d in dirs:
            p = d + "/" + base
            if os.path.exists(p + "/__init__.py"):
                return p + "/__init__.py"
            if os.path.exists(p + ".py"):
                return p + ".py"
        found: list[str] = []
        for d in dirs:
            if os.path.exists(d + "/" + base):
                found.append(d + "/" + base)
        return ":".join(found)

    def find(self, name: str, line: int) -> Mod:
        # the user module called name, loaded with its parent packages unless it is already
        if name == "ffi" and line >= LINES and self.in_lib(FILES[line // LINES]):
            # (a module of Pystachy's lib/, such as pyobj, that declares C functions, and a program with an
            # ffi module of its own, which the driver lets replace the builtin one, as CPython would)
            lib = FILES[line // LINES]
            fail(f"module '{lib[lib.rfind('/') + 1 : -3]}' needs Pystachy's builtin ffi module, which the program's own {self.modpath(name)} replaces: rename that module", line)
        if name in self.mods:
            return self.mods[name]
        dot = name.rfind(".")
        if dot >= 0:
            par = self.find(name[:dot], line)
            if par.pdir == "":
                fail(f"No module named '{name}'; '{par.name}' is not a package", line)
            if name in self.mods:
                return self.mods[name]  # the package's own code imported it
        p = self.modpath(name)
        if p == "":
            # (an optional import other than try: <imports> / except ImportError:, which optional() decides)
            hint = "; an optional import is supported only as try: <imports> / except ImportError: (except clauses naming only ImportError or ModuleNotFoundError, and no finally)" if self.optry else ""
            if name in CBUILTIN and self.filepath(name) != "":
                fail(f"module '{name}' is not supported: it is built into CPython, which imports it rather than the {name} module on the module path, and Pystachy does not have it{hint}", line)
            fail(f"module '{name}' is not supported: it is not a builtin module ({', '.join([k for k in MODULES.keys() if k != 'ffi' and k != TYPESMOD and k != IOMOD])}) and there is no {name[dot + 1 :]}.py on the module path{hint}", line)
        if p.endswith("/__init__.py"):
            return self.load(name, p, p[:-12])
        if p.endswith(".py"):
            return self.load(name, p, "")
        # a namespace package: a directory without __init__.py
        m = Mod(name, "", p)
        self.mods[name] = m
        self.order.append(m)
        return m

    def load(self, name: str, path: str, pdir: str) -> Mod:
        m = Mod(name, path, pdir)
        self.mods[name] = m
        m.body = self.parse(path)
        del self.parsed[path]  # (m rewrites its tree: the file imported under another name is parsed again)
        self.prescan(m)
        r: list[Node] = []
        if self.init_raise(m, m.body.kids, r, True):
            r[0].s = "init"  # (an optional import of the module returns there instead: Gen.raise_stmt)
            m.fails = import_error(r[0].kids[0])
        self.simplify(m, m.body, {})
        self.docstring(m)
        self.bindings(m)
        sure = self.sure
        maybe = self.maybe
        self.sure = m.sure
        self.maybe = m.maybe
        self.imports(m, m.body, False)
        self.namedtuples(m)
        self.sure = sure
        self.maybe = maybe
        m.done = True
        if self.in_lib(path):
            for k in m.kinds.values():
                if k == "b:ffi" or k.startswith("b:ffi."):
                    GLUE[name] = self.public(m)
        self.order.append(m)
        return m

    def in_lib(self, path: str) -> bool:
        # a file of Pystachy's own lib/ (the last directory of the module path)
        lib = self.dirs[-1] if len(self.dirs) > 0 else ""
        lib = lib[2:] if lib.startswith("./") else lib
        path = path[2:] if path.startswith("./") else path
        return lib != "" and path.startswith(lib + "/")

    def parse(self, path: str) -> Node:
        # a module's file, parsed once for the looks before it is loaded (optional()) and the load
        if path in self.parsed:
            return self.parsed[path]
        f = open(path, "r", encoding=RAW)
        src = f.read()
        f.close()
        k = len(FILES)
        FILES.append(path[2:] if path.startswith("./") else path)
        self.parsed[path] = Parser(Lexer(src, k * LINES + 1).file()).module()
        tb_import(self.parsed[path])
        cm_methods(self.parsed[path], cm_names(self.parsed[path]))
        return self.parsed[path]

    def bindings(self, m: Mod) -> None:
        # the names m's top-level code binds (imports of user modules are added by imports())
        count = top_bindings(m.body.kids)
        aliases: list[Node] = []
        for st in m.body.kids:
            k = st.kind
            src = m.kinds.get(st.kids[1].s, "") if k == "assign" and len(st.kids) == 2 and st.kids[1].kind == "name" else ""
            if src != "" and st.kids[0].kind == "name" and (src == "f" or src == "c" or src.startswith("a:")) and count[st.kids[0].s] == 1:
                # name = a def or class of this module (or an alias of one): an alias, if nothing
                # else binds name
                m.kinds[st.kids[0].s] = src if src.startswith("a:") else "a:" + m.q + st.kids[1].s
                aliases.append(st)
            elif k == "def" or k == "class" or k == "subclass":
                m.kinds[st.s] = "f" if k == "def" else "c"
                if k == "subclass" and (len(st.kids) == 2 or st.kids[1].kind == "typeparams") and "__class_getitem__" not in top_bindings(st.kids[0].kids[0].kids):
                    m.cbases[st.s] = st.kids[1]
                for d in [st] if k == "def" else st.kids[0].kids if k == "class" else st.kids[0].kids[0].kids:
                    if d.kind == "def":
                        ga: dict[str, bool] = {}
                        global_assigns(d.kids[2].kids, ga)
                        for nm in ga:
                            m.fnglobal[nm] = True
                            if nm not in m.kinds:
                                m.kinds[nm] = "v"
                                m.fnonly[nm] = True
            elif k == "typealias":
                # type X = value: a type alias if nothing else binds X (see qstmts and Gen.program)
                aliases.append(st)
                m.kinds[st.s] = m.kinds.get(st.s, "v")
            elif k != "import":
                names: dict[str, bool] = {}
                collect([st], names)
                for nm in names:
                    m.kinds[nm] = "v"
                    if nm in m.fnonly:
                        del m.fnonly[nm]
                if k == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[1].kind == "call":
                    # (T = TypeVar("T"), also more than once: see Loader.typevar)
                    if st.kids[0].s not in m.tvars:
                        m.tvars[st.kids[0].s] = []
                    m.tvars[st.kids[0].s].append(st.kids[1].kids[0])
        for nm in m.tvars:
            if len(m.tvars[nm]) != count[nm]:
                m.tvars[nm] = []  # (another statement binds it too)
        for al in aliases:
            if al.kind == "typealias":
                if count[al.s] == 1 and al.s not in m.fnglobal and len(al.kids) > 0:
                    m.kinds[al.s] = "t:" + self.qual(m, al.s)
                    m.taliases[self.qual(m, al.s)] = al
                    self.aliased[m.name + " " + al.s] = al
            elif al.kids[0].s in m.fnglobal:
                m.kinds[al.kids[0].s] = "v"  # a function's global statement rebinds it
            else:
                al.kind = "pass"
                self.used_before(m, al)

    def nt_func(self, m: Mod, e: Node) -> bool:
        # does e, in the top-level code of module m, name lib's collections.namedtuple
        if e.kind == "name":
            return m.kinds.get(e.s, "") == "a:collections$namedtuple"
        return e.kind == "attr" and e.s == "namedtuple" and e.kids[0].kind == "name" and m.kinds.get(e.kids[0].s, "") == "m:collections"

    def namedtuples(self, m: Mod) -> None:
        # NAME = namedtuple(...) in the top-level code of module m, a call of lib's
        # collections.namedtuple once m's imports are bound: the class statement of the class it
        # makes (nt_class). NAME.f.__doc__ = "..." of a field f of it is dropped, as simplify()
        # drops NAME.__doc__ = ...: Pystachy keeps no docstrings of classes. NAME = C of such a
        # class C is an alias, as bindings() makes one of a class statement's
        lib = self.mods.get("collections", None)
        if len(self.dirs) == 0 or lib is None or lib.path != self.dirs[-1] + "/collections/__init__.py":
            return
        if len([st for st in m.body.kids if st.kind == "assign" and st.kids[-1].kind == "call" and self.nt_func(m, st.kids[-1].kids[0])]) == 0:
            return
        count = top_bindings(m.body.kids)
        dels: dict[str, bool] = {}
        deleted(m.body.kids, dels)
        fields: dict[str, list[str]] = {}
        out: list[Node] = []
        for st in m.body.kids:
            v = st.kids[-1] if st.kind == "assign" else st
            t = st.kids[0] if st.kind == "assign" and len(st.kids) == 2 else st
            if st.kind == "assign" and v.kind == "call" and self.nt_func(m, v.kids[0]):
                if t.kind != "name" or count.get(t.s, 0) != 1 or t.s in m.fnglobal or t.s in dels:
                    fail("namedtuple() is only supported as NAME = namedtuple(...), where nothing else binds NAME", st.line)
                c = self.nt_class(t.s, v)
                fields[t.s] = [x.s for x in c.kids[1].kids[0].kids]
                m.kinds[t.s] = "c"
                if t.s in m.tvars:
                    del m.tvars[t.s]  # (no TypeVar)
                out.append(c)
                continue
            if t.kind == "attr" and t.s == "__doc__" and t.kids[0].kind == "attr" and t.kids[0].kids[0].kind == "name" and t.kids[0].kids[0].s in fields and t.kids[0].s in fields[t.kids[0].kids[0].s]:
                if v.kind != "str":
                    fail(f"assigning the __doc__ of namedtuple field {t.kids[0].kids[0].s}.{t.kids[0].s} is only supported with a string literal (Pystachy keeps no docstrings of classes)", st.line)
                continue
            if t is not st and t.kind == "name" and v.kind == "name" and v.s in fields and count.get(t.s, 0) == 1 and t.s not in m.fnglobal:
                m.kinds[t.s] = "a:" + m.q + v.s
                st.kind = "pass"
                self.used_before(m, st)
            out.append(st)
        m.body.kids = out

    def nt_class(self, name: str, v: Node) -> Node:
        # (namedtuples) the class that NAME = namedtuple(typename, field_names, *, rename=False,
        # defaults=None, module=None), call v, makes: given literal arguments (field_names a string
        # or a list or tuple of strings; defaults None or a list or tuple of constants), the
        # statement of a class whose __init__ takes the fields, unannotated, and assigns them (a
        # class template: each call types its fields), and whose base, a "namedtuple" node, holds
        # its name, fields, defaults and module for Gen.program; CPython's errors of the call,
        # raised as the module is imported, are reported here
        line = v.line
        args: dict[str, Node] = {}
        pos = [a for a in v.kids[1:] if a.kind != "kw"]
        for a in v.kids[1:]:
            if a.kind == "starred" or a.kind == "dstar":
                fail("namedtuple() with * or ** arguments is not supported: the compiler makes the class from literal arguments", line)
        if len(pos) > 2:
            fail(f"namedtuple() takes 2 positional arguments but {len(pos)} were given", line)
        for i in range(len(pos)):
            args[["typename", "field_names"][i]] = pos[i]
        for a in v.kids[1:]:
            if a.kind == "kw" and a.s not in ["typename", "field_names", "rename", "defaults", "module"]:
                fail(f"namedtuple() got an unexpected keyword argument '{a.s}'", line)
            if a.kind == "kw" and a.s in args:
                fail(f"namedtuple() got multiple values for argument '{a.s}'", line)
            if a.kind == "kw":
                args[a.s] = a.kids[0]
        missing = [w for w in ["typename", "field_names"] if w not in args]
        if len(missing) > 0:
            fail(f"namedtuple() missing {len(missing)} required positional argument{'s' if len(missing) > 1 else ''}: '" + "' and '".join(missing) + "'", line)
        tn = args["typename"]
        fn = args["field_names"]
        if tn.kind != "str":
            fail("namedtuple() is only supported with a string literal as its typename (the compiler makes the class)", line)
        for nm in [tn.s] + [x.s for x in [fn] + fn.kids if x.kind == "str"]:
            if len([c for c in nm if ord(c) >= 128]) > 0:
                fail("namedtuple() of a typename or field name with non-ASCII characters is not supported", line)
        if (fn.kind != "str" and fn.kind != "list" and fn.kind != "tuple") or any(x.kind != "str" for x in fn.kids):
            fail("namedtuple() is only supported with field names that are a string literal or a list or tuple of string literals (the compiler makes the class)", line)
        names: list[str] = fn.s.replace(",", " ").split() if fn.kind == "str" else [x.s for x in fn.kids]
        rn = args.get("rename", mk("False", "", line, []))
        dn = args.get("defaults", mk("None", "", line, []))
        rep = 1
        if dn.kind == "binop" and dn.s == "*" and dn.kids[1].kind == "int" and (dn.kids[0].kind == "list" or dn.kids[0].kind == "tuple"):
            rep = int(dn.kids[1].s)  # ([None] * 4: dis.py's)
            dn = dn.kids[0]
        mn = args.get("module", mk("None", "", line, []))
        if rn.kind != "True" and rn.kind != "False":
            fail("namedtuple() is only supported with rename=True or rename=False", line)
        if (dn.kind != "None" and dn.kind != "list" and dn.kind != "tuple") or len([x for x in dn.kids if not is_const(x)]) > 0:
            fail("namedtuple() is only supported with defaults=None or a list or tuple of constants (numbers, strings, True, False, None)", line)
        if mn.kind != "None" and mn.kind != "str":
            fail("namedtuple() is only supported with module=None or a string literal", line)
        seen: dict[str, bool] = {}
        for i in range(len(names) if rn.kind == "True" else 0):
            nm = names[i]
            if not ascii_ident(nm) or nm in KEYWORDS or nm.startswith("_") or nm in seen:
                names[i] = f"_{i}"
            seen[nm] = True
        for nm in [tn.s] + names:
            if not ascii_ident(nm):
                fail(f"Type names and field names must be valid identifiers: {nm!r}", line)
            if nm in KEYWORDS:
                fail(f"Type names and field names cannot be a keyword: {nm!r}", line)
        seen = {}
        for nm in names:
            if nm.startswith("_") and rn.kind != "True":
                fail(f"Field names cannot start with an underscore: {nm!r}", line)
            if nm in seen:
                fail(f"Encountered duplicate field name: {nm!r}", line)
            seen[nm] = True
        if len(dn.kids) * rep > len(names):
            fail("Got more default values than field names", line)
        dn = mk("list", "", line, dn.kids * rep if rep > 0 else [])
        if len(names) == 0:
            fail("a namedtuple without fields is not supported", line)
        params = mk("params", "0,-1", line, [mk("param", "_cls", line, [mk("noann", "", line, []), mk("noann", "", line, [])])])
        body: list[Node] = []
        k = len(names) - len(dn.kids)
        for i in range(len(names)):
            params.kids.append(mk("param", names[i], line, [mk("noann", "", line, []), clone(dn.kids[i - k]) if i >= k else mk("noann", "", line, [])]))
            body.append(mk("assign", "", line, [mk("attr", names[i], line, [mk("name", "_cls", line, [])]), mk("name", names[i], line, [])]))
        init = mk("def", "__init__", line, [params, mk("noann", "", line, []), mk("block", "", line, body)])
        info = mk("namedtuple", tn.s, line, [mk("tuple", "", line, [mk("str", nm, line, []) for nm in names]), mk("tuple", "", line, [clone(x) for x in dn.kids]), mn])
        return mk("subclass", name, line, [mk("class", name, line, [mk("block", "", line, [init])]), info])

    def late_aliases(self, m: Mod) -> None:
        # name = f where an import binds f (from m import f): an alias too, if nothing else binds
        # name; so are name = <a type> and name: TypeAlias = <a type> (type_value), type aliases,
        # and name: TypeAlias = C of a def or class (as name = C)
        count = top_bindings(m.body.kids)
        dm = self.dm
        self.dm = m
        for st in m.body.kids:
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[1].kind == "name":
                src = m.kinds.get(st.kids[1].s, "")
                nm = st.kids[0].s
                if src.startswith("a:") and m.kinds.get(nm, "") == "v" and count.get(nm, 0) == 1 and nm not in m.fnglobal:
                    m.kinds[nm] = src
                    st.kind = "pass"
                    self.aliased[m.name + " " + nm] = st
                    self.used_before(m, st)
            ann = st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name" and self.bpath(st.kids[1]) == "typing.TypeAlias"
            if not ann and not (st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name"):
                continue
            nm = st.kids[0].s
            if m.kinds.get(nm, "") != "v" or count.get(nm, 0) != 1 or nm in m.fnglobal:
                continue
            v = st.kids[-1]
            src = m.kinds.get(v.s, "") if v.kind == "name" else ""
            if ann and (src == "f" or src == "c" or src.startswith("a:")):
                m.kinds[nm] = src if src.startswith("a:") else "a:" + m.q + v.s  # (qstmts drops the statement)
                self.aliased[m.name + " " + nm] = st
                self.used_before(m, st)
            elif not ann and v.kind == "call" and self.typevar(st.kids[0]):
                m.kinds[nm] = "t:" + self.qual(m, nm)  # (T = TypeVar("T"): its imports name it, as a type alias's do)
                self.aliased[m.name + " " + nm] = st
            elif self.type_value(v, True) or (ann and v.kind == "str"):
                # (Gen.program leaves out the assignment unless it binds a class such as int;
                # qstmts makes name: TypeAlias = value an assignment, or a type statement for a
                # string, a forward reference)
                m.kinds[nm] = "t:" + self.qual(m, nm)
                m.taliases[self.qual(m, nm)] = st
                self.aliased[m.name + " " + nm] = st
        self.dm = dm

    def type_value(self, e: Node, top: bool) -> bool:
        # does e, a value that module dm's top-level code assigns, surely evaluate to a type that
        # annotations can name, calling no code of the program: the builtin class int, float, str
        # or bool, a type alias or a TypeVar ("t:"); or, not alone (top), another builtin class,
        # a class, typing's names and None; a subscript of a builtin generic, of typing's or
        # collections.abc's names, of a generic class or a type alias; '|' of those
        k = e.kind
        if k == "name" or k == "attr":
            b = self.kind_of(e)
            if (k == "name" and b == "" and e.s in ["int", "float", "str", "bool"]) or b.startswith("t:"):
                return True
            if top:
                return False
            p = self.bpath(e) if b.startswith("b:") or k == "attr" else ""
            return b == "c" or b.startswith("t:") or self.class_alias(b) or self.typevar(e) or p.startswith("typing.") or (k == "name" and b == "" and e.s in GENERICS + ["object", "bytes", "complex"])
        if k == "binop" and e.s == "|":
            return self.type_value(e.kids[0], False) and self.type_value(e.kids[1], False) and not (e.kids[0].kind == "None" and e.kids[1].kind == "None")
        if k == "index":
            base = e.kids[0]
            p = self.bpath(base)
            ok = (base.kind == "name" and self.kind_of(base) == "" and base.s in GENERICS) or self.kind_of(base).startswith("t:") or self.generic_class(base) or p.startswith("typing.") or p.startswith("collections.abc.")
            return ok and self.type_item(e.kids[1])
        return k == "None" and not top

    def type_item(self, e: Node) -> bool:
        # (type_value) an item of a subscript of a type: also a string (a forward reference), a
        # literal, ..., a list of them (Callable's parameters) or *Ts
        k = e.kind
        if k == "tuple" or k == "list":
            for x in e.kids:
                if not self.type_item(x):
                    return False
            return True
        if k == "starred":
            return self.type_item(e.kids[0])
        if k == "str" or k == "int" or k == "True" or k == "False" or k == "ellipsis":
            return True
        if k == "unary" and e.s == "-" and (e.kids[0].kind == "int" or e.kids[0].kind == "float"):
            return True
        return self.type_value(e, False)

    def class_alias(self, k: str) -> bool:
        # is k, a name's kind, an alias of a class ("a:<qualified name>")
        q = k[2:]
        for x in self.order if k.startswith("a:") else []:
            if q.startswith(x.q) and "$" not in q[len(x.q) :]:
                return x.kinds.get(q[len(x.q) :], "") == "c"
        return False

    def qual(self, m: Mod, s: str) -> str:
        # the qualified name of module m's global s, as qname() makes a variable's
        return "__main__$" + s if m.name == "" and s in PYBUILTINS else m.q + s

    def is_alias(self, m: Mod, st: Node) -> bool:
        # is st, a top-level statement of m, one that binds a type alias (m.taliases)
        nm = st.s if st.kind == "typealias" else st.kids[0].s if (st.kind == "assign" or st.kind == "annassign") and st.kids[0].kind == "name" else ""
        q = self.qual(m, nm) if nm != "" else ""
        return q in m.taliases and m.taliases[q] is st

    def late_takes(self, last: bool) -> bool:
        # from t import x as name took t's variable x, which late_aliases() has since made an alias
        # of a function or class (x = f, f from-imported): name is that alias too, rather than a copy
        # of a variable that t's code no longer assigns, where all the from-imports of variables that
        # bind name there take that alias and nothing else binds it; else, once the last pass finds
        # no other alias to wait for, the import is an error. Did any import change?
        took: dict[str, str] = {}  # (by where and name: the alias they take, "!" for two)
        var: dict[str, bool] = {}  # (and whether one of them takes a variable)
        for n in self.vtaken:
            if n.kids[2].kind == "assign":
                key = n.kids[4].s + " " + n.s
                k = self.mods[n.kids[0].s].kinds.get(n.kids[1].s, "")
                if not k.startswith("a:") and not k.startswith("t:"):
                    var[key] = True
                else:
                    took[key] = k if took.get(key, k) == k else "!"
        changed = False
        for i in range(len(self.vtaken)):
            n = self.vtaken[i]
            cp = n.kids[2]
            k = self.mods[n.kids[0].s].kinds.get(n.kids[1].s, "")
            if cp.kind != "assign" or not (k.startswith("a:") or k.startswith("t:")):
                continue
            key = n.kids[4].s + " " + n.s
            was = n.kids[3].s
            now = self.vtakek[i].get(n.s, "")
            al = self.aliased.get(n.kids[0].s + " " + n.kids[1].s, n)
            msg = ""
            if al is not n and int(n.kids[5].s) > 0 and al.line > int(n.kids[5].s):
                # (taken while t's code ran an import above the alias: CPython raises ImportError)
                what = f" ({n.kids[1].s} = {al.kids[-1].s})" if k.startswith("a:") else ""
                of = "an alias of a function or class" if what != "" else "a TypeVar" if al.kind == "assign" and al.kids[1].kind == "call" else "a type alias"
                msg = f"cannot import name '{n.kids[1].s}' from '{n.kids[0].s}' here: its code binds it{what} only after the import that runs this one (not supported for {of})"
            elif was == "v" or (key in var and last):
                msg = f"'{n.s}' is bound both as a variable and by an import (not supported)"
            elif took[key] == "!" or (was != "" and was != k) or (now != "" and now != "v" and now != k):
                msg = f"'{n.s}' is bound by two imports, to different modules, functions or classes (not supported)"
            elif key in var:
                continue  # (another of them takes a variable, which may yet be found an alias)
            if msg == "":
                self.vtakek[i][n.s] = k
                cp.kind = "pass"
                if not n.kids[4].s.startswith("@") and n.kids[4].s + " " + n.s not in self.fkline:
                    self.fkline[n.kids[4].s + " " + n.s] = n.line  # (the function's import that binds it: qstmts())
            elif not n.kids[4].s.startswith("@"):
                cp.kind = "badimport"  # (in a function: an error where it is compiled)
                cp.s = msg
                cp.kids = []
            else:
                fail(msg, n.line)
            changed = True
        return changed

    def used_before(self, m: Mod, al: Node) -> None:
        # an alias (name = f) binds name for all of the module's code; module-level code that runs
        # before it would see name unbound in CPython (but not a type statement's value, which is
        # evaluated lazily)
        nm = al.kids[0].s
        for st in m.body.kids:
            if st is al:
                return
            if st.kind != "def" and st.kind != "class" and st.kind != "subclass" and st.kind != "typealias" and refers(st, nm):
                fail(f"name '{nm}' is used before '{nm} = {al.kids[-1].s}' binds it (not supported for an alias of a function or class)", st.line)

    def deftime(self, m: Mod, body: list[Node], env: list[dict[str, bool]], cls: str, added: list[str], top: bool) -> None:
        # CPython evaluates a def statement's decorators, defaults and annotations, a class
        # statement's decorators and bases, and runs its body, used or not: what they read must be
        # bound then. env: the names surely bound so far, those bound on some path, then a class
        # body's own (in class body cls). An annotation (unless imported from __future__) needs
        # surely bound names, and what it or a base raises is an error (reads); the rest, in an
        # imported module, may read its variables and functions that may be unbound (checked as
        # they run: Gen.effect, read). added: the names body binds that were not surely bound,
        # unbound after a block (not top) but what both if branches bind
        mod = f"when module '{m.name}' is imported" if m.name != "" else ""
        sure = env[2] if cls != "" else env[0]
        maybe = env[3] if cls != "" else env[1]
        for st in body:
            k = st.kind
            imp = top and cls == "" and m.name != "" and self.called < 2 and has_kind(st, "uimport")
            alias = top and cls == "" and self.is_alias(m, st)  # (a type alias, whose value calls nothing)
            if imp or (top and cls == "" and self.called == 0 and not alias and calls(st, m)):
                # (from a first call on, a function's global statement may bind names; from a first
                # import, a module that imports this one may also assign its builtin names: m.object = 5)
                for nm in m.kinds:
                    if nm in m.fnglobal or (imp and nm in PYBUILTINS):
                        env[1][nm] = True
                        self.known.pop(nm, False)
                self.called = 2 if imp else 1
            for a in st.kids if k == "import" else []:
                self.lazyann = self.lazyann or a.kids[0].s == "__future__.annotations"
            if k == "subclass" and len(st.kids) == 2 and st.kids[1].kind == "name" and st.kids[1].s == "object" and "object" not in env[1] and "object" not in env[3]:
                # class C(object) where object is surely still the builtin: a class without bases
                st.kind = "class"
                st.kids = st.kids[0].kids
                k = "class"
            c = st.kids[0] if k == "subclass" else st
            for x in c.kids[3:] if k == "def" else c.kids[1:] if k == "class" or k == "subclass" else []:
                if x.s.startswith("?"):
                    fail("unsupported decorator: only a dotted name or a call of one is supported (PEP 614)", x.line)
                root = x.s.split(".")[0]
                if root in PYBUILTINS and root not in env[1] and root not in env[3]:
                    self.bdecos[x.line] = True  # (the builtin, whatever the module binds later: qdeco)
                if mod != "" and x.s != "async":
                    self.reads(x.kids[0] if len(x.kids) > 0 else mk("name", root, x.line, []), env, f"CPython evaluates decorator @{x.s} {mod}", 0)
            names: list[str] = []
            plain = False  # (a class without bases, decorators or __class_getitem__: see known)
            if k == "def":
                for p in st.kids[0].kids + [mk("param", "", st.line, [st.kids[1], mk("noann", "", st.line, [])])]:
                    self.ann(p.kids[0], env, "the def statement")
                    if mod != "":
                        self.reads(p.kids[1], env, f"CPython evaluates this default value {mod}", 0)
            elif k == "class" or k == "subclass":
                inner: dict[str, bool] = {"__module__": True, "__qualname__": True}  # (and a generic class's type parameters)
                mark((st.kids[1].s if k == "subclass" and st.kids[1].kind == "typeparams" else "").split() + (["__annotations__"] if has_kind(c.kids[0], "annassign") else []), inner, {}, [])
                tps: list[str] = []
                mark((st.kids[1].s if k == "subclass" and st.kids[1].kind == "typeparams" else "").split(), env[2], {}, tps)
                tpouter = self.tpnames
                self.tpnames = dict(tpouter)
                for t in (st.kids[1].s if k == "subclass" and st.kids[1].kind == "typeparams" else "").split():
                    self.tpnames[t] = True
                for b in st.kids[1:] if k == "subclass" else []:
                    # (where the class statement is, with its type parameters; in the main program
                    # too, where a base is an error later: CPython's comes first)
                    self.reads(b, env, f"CPython evaluates the bases of class {st.s}" + (" " + mod if mod != "" else ""), 1)
                for t in tps:
                    env[2].pop(t, False)
                own = dict(inner)
                self.deftime(m, c.kids[0].kids, [env[0], env[1], inner, own], st.s, [], True)
                self.tpnames = tpouter
                plain = top and cls == "" and k == "class" and len(st.kids) == 1 and "__class_getitem__" not in own
            elif k == "annassign" or (alias and k == "assign"):
                if alias and st.kids[-1].kind != "str":
                    self.reads(st.kids[-1], env, "CPython evaluates this type alias's value when the assignment runs", 3)
                if k == "annassign":
                    self.ann(st.kids[1], env, "the class body" if cls != "" else "the annotated assignment")
            first: dict[str, bool] = {}
            for i in range(len(st.kids) if k != "def" and k != "class" and k != "subclass" and k != "typealias" else 0):
                x = st.kids[i]
                tgt: list[str] = [x.s] if x.kind == "except" and x.s != "" else []
                if x.kind == "block" or x.kind == "except":
                    # (a for's, with's or except's name is bound in its block; after an if, what both bind)
                    if k == "for" and i == 2:
                        names_in(st.kids[0], tgt)
                    for w in st.kids if k == "with" else []:
                        if w.kind == "withitem" and len(w.kids) == 2:
                            names_in(w.kids[1], tgt)
                    inside: list[str] = []
                    mark(tgt, sure, maybe, inside)
                    for nm in tgt if cls == "" else []:
                        self.known.pop(nm, False)
                    self.deftime(m, x.kids if x.kind == "block" else x.kids[1].kids, env, cls, inside, False)
                    for nm in inside:
                        sure.pop(nm, False)
                        if k == "if" and i == 1:
                            first[nm] = True
                        elif k == "if" and nm in first:
                            names.append(nm)
                elif (k == "annassign" and i == 1) or k == "global" or k == "nonlocal":
                    continue
                elif ((k == "assign" or k == "pass") and i < len(st.kids) - 1) or ((k == "annassign" or k == "for") and i == 0):
                    names_in(x, names if k != "for" and (k != "annassign" or len(st.kids) == 3) else tgt)  # (an alias is a "pass")
                elif k == "import":
                    names.extend([x.s] if x.kids[0].s != "builtins." + x.s else [])  # (from builtins import len rebinds nothing)
                elif k == "del":
                    names_in(x, tgt)
                    for nm in tgt:
                        sure.pop(nm, False)
                        if cls == "":
                            self.known.pop(nm, False)
                        if top:
                            maybe.pop(nm, False)  # (surely unbound)
                else:
                    if k == "augassign" and i == 0:
                        names_in(x, names)
                    if cls != "" and mod != "":
                        # (what a class body's other statements read)
                        self.reads(x.kids[0] if x.kind == "withitem" else x, env, f"CPython runs this statement of the body of class {cls} {mod}", 0)
            bound = names + (st.s.split() if k == "def" or k == "class" or k == "subclass" or k == "uimport" or k == "typealias" else [])
            mark(bound, sure, maybe, added)
            for nm in bound if cls == "" else []:
                self.known.pop(nm, False)
            if plain:
                self.known[st.s] = True

    def ann(self, n: Node, env: list[dict[str, bool]], where: str) -> None:
        # an annotation, which CPython evaluates when where runs unless the module imports
        # annotations from __future__ (a string is a forward reference)
        if not self.lazyann:
            self.reads(n, env, f"CPython evaluates this annotation when {where} runs: quote it, or import annotations from __future__", 3)

    def reads(self, e: Node, env: list[dict[str, bool]], what: str, how: int) -> None:
        # the names expression e reads, which must be bound where CPython evaluates it (what): not
        # those of a lambda's body or of a comprehension's own scope. e is (how) 0 a value, 1 a
        # base or part of one, 2 part of an annotation, 3 an annotation. Operands come first, as
        # CPython evaluates them: in a base or an annotation, what raises then (type_error()) is
        # CPython's error; an annotation reads surely bound names and must be a type (not_type)
        k = e.kind
        nm = e.s
        tps: list[str] = []
        mark(nm.split() if k == "noann" else [], env[2], {}, tps)  # (a generic def's type parameters: Parser.funcdef)
        outer = self.tpnames
        if k == "noann":
            self.tpnames = dict(outer)
            for t in nm.split():
                self.tpnames[t] = True
        if k == "name" and "$" not in nm and nm not in env[0] and nm not in env[2] and nm not in PYBUILTINS and nm not in MODNAMES:
            maybe = nm in env[1] or nm in env[3]
            if how >= 2 or (self.dm.kinds.get(nm, "") != "v" and self.dm.kinds.get(nm, "") != "f"):
                fail(f"name '{nm}' {'may be unbound, which is not supported' if maybe else 'is not defined'} ({'import it from typing' if how >= 2 and nm in TYPING else what})", e.line)
        for kid in e.kids[2:3] if k == "listcomp" or k == "asynccomp" else [] if k == "lambda" else e.kids:
            self.reads(kid, env, what, how if how < 3 or k == "noann" else 2)
        self.tpnames = outer
        why = self.type_error(e, env) if how > 0 else ""
        for t in tps:
            env[2].pop(t, False)
        if why != "":
            fail(f"{why} ({what})", e.line)
        if how >= 2 and not (k == "name" and nm in self.tpnames) and self.not_type(e, how == 3):
            fail(f"an annotation that is not a type is not supported: only classes, typing's names, their subscripts and '|' of them ({what})", e.line)
        if how >= 2 and k == "attr":
            e.chk = True  # (an attribute a module lacks is CPython's AttributeError: qann)

    def type_error(self, e: Node, env: list[dict[str, bool]]) -> str:
        # the TypeError CPython raises evaluating e, a subscript or '|' whose operands it has
        # evaluated (as far as evaltype() knows them), or ""
        k = e.kind
        if k != "index" and not (k == "binop" and e.s == "|"):
            return ""
        ts = [self.evaltype(x, env) for x in e.kids]
        if k == "index" and ts[0] == "type":
            return f"type '{e.kids[0].s}' is not subscriptable"
        have = len(e.kids[1].kids) if k == "index" and e.kids[1].kind == "tuple" else 1
        want = {"typing.Optional": 1, "typing.List": 1, "typing.Dict": 2}.get(ts[0], have) if k == "index" else have
        if want != have and ts[0] == "typing.Optional":
            return "typing.Optional requires a single type"  # (CPython adds the arguments' reprs)
        if want != have:
            return f"Too {'many' if have > want else 'few'} arguments for {ts[0]}; actual {have}, expected {want}"
        if k == "binop" and "" not in ts and not ts[0].startswith("typing.") and not ts[1].startswith("typing.") and ("str" in ts or (ts[0] == "NoneType" and ts[1] == "NoneType")):
            return f"unsupported operand type(s) for |: '{ts[0]}' and '{ts[1]}'"
        return ""

    def evaltype(self, e: Node, env: list[dict[str, bool]]) -> str:
        # what operand e of a subscript or '|' evaluates to, as far as type_error() needs it: "type" (a
        # builtin class, or a class of the module that is in known), "str", "NoneType", a typing
        # name ("typing.Optional"), or "" if it may be anything else
        if e.kind == "str" or e.kind == "None":
            return "str" if e.kind == "str" else "NoneType"
        if e.kind != "name" or e.s in env[2] or e.s in env[3]:
            return ""  # (a class body's or a type parameter)
        if e.s in self.known or (e.s in ["int", "float", "str", "bool", "bytes", "object", "complex"] and e.s not in env[1]):
            return "type"
        b = self.kind_of(e)
        return b[2:] if b.startswith("b:typing.") else ""

    def not_type(self, e: Node, top: bool) -> bool:
        # may annotation node e (top: the whole annotation) run code of the program, or raise,
        # when CPython evaluates it: a variable (but as the whole annotation, an alias, whose value
        # is only stored), a call, an operator but '|' of types, a subscript of what is not
        # typing's or a builtin generic
        k = e.kind
        b = e.kids[0] if k == "index" or k == "binop" or k == "unary" else e
        if k == "binop":
            return e.s != "|" or b.kind not in ANNKINDS[:5] or e.kids[1].kind not in ANNKINDS[:5]
        if k == "unary":
            return e.s != "-" or (b.kind != "int" and b.kind != "float")  # (Literal[-1])
        if k == "index" and (self.kind_of(b) == "c" or self.kind_of(b).startswith("a:")) and self.generic_class(b):
            return False
        if k == "index" and (b.kind not in ANNKINDS[:2] or self.kind_of(b) == "f" or self.kind_of(b) == "c" or self.kind_of(b).startswith("a:")):
            return True
        p = self.bpath(e) if k == "attr" else ""
        if p.startswith("ffi.") and (p[4:] in CTYPES or p[4:] in ("c_buf", "c_float")):
            return False  # (the same C type as a from-ffi import, including module aliases)
        if p != "" and not p.startswith("typing.") and p != "os.PathLike" and p != "collections.abc" and not (p.startswith("collections.abc.") and p[16:] in ABCS) and p != "dataclasses.KW_ONLY":
            return True  # (a builtin module may lack the attribute)
        return k not in ANNKINDS or (self.kind_of(b) == "v" and not (top and k == "name") and not (k == "name" and self.typevar(e))) or (k == "index" and self.kind_of(b) == "" and b.s in PYBUILTINS and b.kind == "name" and b.s not in GENERICS)

    def generic_class(self, b: Node) -> bool:
        # is b (a name, an alias such as an imported class's, or a user module's attribute, that
        # names a class) a class whose one base is typing.Generic[...]
        m = self.dm
        name = b.s
        k = self.kind_of(b)
        if k.startswith("a:"):
            # (a:<module's prefix><name>: a def or class of that module)
            name = k[2:]
            for x in self.mods:
                q = self.mods[x].q
                if q != "" and k[2:].startswith(q) and "$" not in k[2 + len(q):]:
                    m = self.mods[x]
                    name = k[2 + len(q):]
        elif b.kind == "attr":
            k = self.kind_of(b.kids[0])
            m = self.mods[k[2:]] if k.startswith("m:") and k[2:] in self.mods else self.dm
        base = m.cbases.get(name, None)
        if base is not None and base.kind == "typeparams":
            return True  # (class C[T])
        if base is None or base.kind != "index":
            return False
        g = base.kids[0]
        if g.kind == "name":
            k = m.kinds.get(g.s, "")
            return k == "b:typing.Generic" or k == "b:typing_extensions.Generic"
        if g.kind == "attr" and g.s == "Generic" and g.kids[0].kind == "name":
            k = m.kinds.get(g.kids[0].s, "")
            return k == "b:typing" or k == "b:typing_extensions"
        return False

    def bpath(self, e: Node) -> str:
        # what a name or an attribute chain on one names in a builtin module ("collections.abc.Mapping"), or ""
        k = self.kind_of(e)
        if k.startswith("b:") or e.kind == "name":
            return k[2:] if k.startswith("b:") else ""  # (also a user module's attribute: collections.abc)
        p = self.bpath(e.kids[0]) if e.kind == "attr" else ""
        return p + "." + e.s if p != "" else ""

    def typevar(self, e: Node) -> bool:
        # is name e a module global that only e = TypeVar(...) (or TypeVarTuple(...)) statements
        # bind, typing's (each one is Gen.typevar_def's): '|' of it and subscripts holding it run
        # typing's code
        if e.s not in self.dm.tvars or len(self.dm.tvars[e.s]) == 0 or e.s in self.dm.fnglobal:
            return False
        for c in self.dm.tvars[e.s]:
            if self.bpath(c) != "typing.TypeVar" and self.bpath(c) != "typing.TypeVarTuple":
                return False
        return True

    def kind_of(self, e: Node) -> str:
        # what a name, or an attribute of a user module (a.b), is bound to in module dm, or ""
        if e.kind == "name":
            return self.dm.kinds.get(e.s, "")
        b = self.kind_of(e.kids[0]) if e.kind == "attr" else ""
        return self.mods[b[2:]].kinds.get(e.s, "") if b.startswith("m:") and b[2:] in self.mods else ""

    def simplify(self, m: Mod, blk: Node, scope: dict[str, bool]) -> None:
        # what the loader decides about blk before anything else (scope: the names that the function
        # or class blk is in binds itself, which hide the module's): the if statements and optional
        # imports CPython decides at import time (static_if(), optional()) leave what runs in their
        # place; a module-level alias of a def or class (bisect = bisect_right) binds the same
        # function or class, and is no statement at run time
        out: list[Node] = []
        added: list[str] = []  # (what an import in blk binds is sure only within blk)
        for i in range(len(blk.kids)):
            st = blk.kids[i]
            if blk is m.body:
                self.pos = i
            if blk is m.body and st.kind == "assign" and st.kids[0].kind == "name" and st.kids[0].s in m.flagat and m.flagat[st.kids[0].s] == i:
                # (name = <a test of the platform>: the bool it is, as a literal, platform_flags())
                st.kids[1] = mk("True" if m.flagval[st.kids[0].s] == 1 else "False", "", st.line, [])
            self.fold_tests(m, st, scope)
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "attr" and st.kids[0].s == "__doc__" and st.kids[0].kids[0].kind == "name" and blk is m.body:
                # f.__doc__ = g.__doc__: the docstrings of functions and classes cannot be read in
                # Pystachy, so this is dropped; a read of a module's __doc__ that it assigns is an error
                self.docsets.append(mk("docset", st.kids[0].kids[0].s, st.line, []))
                self.docsetm.append(m)
                continue
            run: list[Node] = []
            if self.static_if(m, st, scope, run) or self.optional(m, st, run, False) or (blk is m.body and self.unbound_try(m, st, out, blk.kids[i + 1 :], run)):
                b = mk("block", "", st.line, run)
                self.simplify(m, b, scope)
                out.extend(b.kids)
            else:
                out.append(st)
                for a in st.kids if st.kind == "import" and blk is not m.body else st.kids[:0]:
                    if special_import(st, a) and a.s not in self.fsure:
                        self.fsure[a.s] = True
                        added.append(a.s)
                c = st.kids[0] if st.kind == "subclass" else st  # (class C(object) too: see deftime)
                inner = scope_names(c) if c.kind == "def" or c.kind == "class" else scope
                decl: dict[str, bool] = {}
                types: dict[str, Node] = {}
                held: dict[str, int] = {}
                pos = self.pos
                fs = self.fs
                fsure = self.fsure
                incls = self.incls
                if st.kind == "def":
                    globals_in(st.kids[2].kids, decl)
                    local_types(st.kids[2].kids, types)
                    self.pos = -1
                    self.fs = own_specials(st)
                    self.fsure = {}
                elif c.kind == "class":
                    self.incls = True
                    scope_globals(c.kids[0].kids, held)
                for kid in c.kids:
                    if kid.kind == "block":
                        self.simplify(m, kid, inner)
                    elif kid.kind == "except":
                        self.simplify(m, kid.kids[1], inner)
                self.pos = pos
                self.fs = fs
                self.fsure = fsure
                self.incls = incls
                if st.kind == "def":
                    self.dropped_locals(st, inner, decl, types)
                elif c.kind == "class":
                    self.dropped_globals(c, held)
        for nm in added:
            del self.fsure[nm]
        blk.kids = out

    def fold_tests(self, m: Mod, n: Node, scope: dict[str, bool]) -> None:
        # the conditional expressions in n, but in its blocks (which simplify() takes), lambdas and
        # comprehensions, whose test decide() decides with nothing else to run: what runs, in place
        for i in range(len(n.kids)):
            k = n.kids[i]
            while k.kind == "ifexp":
                pre: list[Node] = []
                r = self.decide(m, k.kids[0], scope, pre)
                if r < 0 or len(pre) > 0:
                    break
                k = k.kids[1] if r == 1 else k.kids[2]
                n.kids[i] = k
            if k.kind != "block" and k.kind != "except" and k.kind != "lambda" and k.kind != "listcomp" and k.kind != "asynccomp":
                self.fold_tests(m, k, scope)

    def dropped_globals(self, c: Node, held: dict[str, int]) -> None:
        # a global statement in class c's body holds for the whole body in CPython, also in code
        # simplify() dropped (held: the names the body declared global before, each with its
        # statement's line), so x = 2 further on binds the module's x: such a statement is kept,
        # and the class is the error that a global statement in a class body is
        now: dict[str, int] = {}
        scope_globals(c.kids[0].kids, now)
        kept: list[Node] = []
        for nm in held:
            if nm not in now:
                kept.append(mk("global", "", held[nm], [mk("name", nm, held[nm], [])]))
        c.kids[0].kids = kept + c.kids[0].kids

    def dropped_locals(self, d: Node, before: dict[str, bool], decl: dict[str, bool], types: dict[str, Node]) -> None:
        # what function d binds only in code simplify() dropped still decides its scope in CPython: a
        # global statement there holds for the whole function (it is kept), and a name bound there is
        # a local that nothing binds, so a read of it raises UnboundLocalError. It is declared, with
        # the type of a binding that was dropped (types: x: T, or x = <constant>), as x: T declares
        # it; if none gives one, it is an error where d is compiled
        now: dict[str, bool] = {}
        globals_in(d.kids[2].kids, now)
        pre: list[Node] = []  # (the statements put first, each before the ones so far)
        for nm in decl:
            if nm not in now:
                pre.append(mk("global", "", d.line, [mk("name", nm, d.line, [])]))
        now = scope_names(d)  # (without pre's global statements, which only take decl's names out: before has none)
        read: dict[str, bool] = {}
        for nm in before:
            if nm not in now:
                read_names(d.kids[2], read)  # (one walk of the body, not one for each name)
                break
        for nm in before:
            msg = f"'{nm}' is local to {d.s}() only through code that is dropped at compile time (for the platform, TYPE_CHECKING or an import that fails), so a read of it raises UnboundLocalError; that is supported only where the dropped code annotates it with a supported type or assigns it a constant"
            if nm not in now and nm in read and nm in types:
                # (where the type is not supported, the message is msg: Gen.stmt())
                t = types[nm]
                pre.append(mk("annassign", msg, t.line, [mk("name", nm, t.line, []), t]))
            elif nm not in now and nm in read:
                pre.append(mk("badimport", msg, d.line, []))
        d.kids[2].kids = [pre[len(pre) - 1 - i] for i in range(len(pre))] + d.kids[2].kids
        early: dict[str, bool] = {}
        user: dict[str, bool] = {}
        import_reads(d.kids[2], {}, early, user)
        self.unsure[str(d.line)] = {}
        for nm in early:
            if nm in user:
                self.unsure[str(d.line)][nm] = True

    def static_if(self, m: Mod, st: Node, scope: dict[str, bool], out: list[Node]) -> bool:
        # an if statement CPython decides at import time, as Pystachy does at compile time: a test of
        # the platform, of TYPE_CHECKING, in an imported module of __name__ == "__main__" or in module
        # code outside class bodies of False or 0 (decide()). Appends what runs to out; False if st
        # is none of these
        if st.kind != "if":
            return False
        pre: list[Node] = []
        r = self.decide(m, st.kids[0], scope, pre)
        if r < 0:
            return False
        out.extend(pre)
        out.extend(st.kids[1].kids if r == 1 else st.kids[2].kids)
        return True

    def optional(self, m: Mod, st: Node, out: list[Node], scan: bool) -> bool:
        # try: <imports, then other statements> / except ImportError: <handler> (an optional module,
        # accel_try()), decided at compile time: the imports run in order until one fails, because
        # its module is not found (the code of its packages runs first), because the module's code
        # raises ImportError at its top level (init_raise(): its code before the raise runs, guarded
        # so that it returns there), or because a from-import names what its module neither binds
        # nor has as a submodule. Then the handler that catches the exception runs; if none fails,
        # the rest of the body and the else block do. Appends what runs to out; False if st is not
        # such a try. Unless scan (init_raise() looking ahead), guarded() checks it later
        if not accel_try(st):
            return False
        line = st.line
        site = mk("pass", "", line, [])  # (for guarded(), which may make it an error)
        out.append(site)
        run: list[Node] = []  # the imports that succeed, then the one that fails
        bad = ""  # the module whose import fails
        exc = "ModuleNotFoundError"
        named = ""  # or the name a from-import of module bad fails to bind
        n = 0  # the import statements that run
        for x in st.kids[0].kids:
            if x.kind != "import" or bad != "":
                break
            n += 1
            ok: list[Node] = []
            p = ""
            for a in x.kids:
                p = a.kids[1].s if not x.s.startswith("from.") else self.relative(m, x.s, a.kids[1].s, x.line)
                i = 0
                while i >= 0 and bad == "" and not builtin_import(x, a) and (len(ok) == 0 or x.s == ""):
                    # each package on the way, then the module (once for a from-import), up to a
                    # builtin submodule (import collections.abc)
                    i = p.find(".", i + 1)
                    q = p[:i] if i >= 0 else p
                    if builtin_module(q):
                        break
                    f = self.init_fails(q) if self.modpath(q) != "" else "ModuleNotFoundError"
                    if f != "":
                        bad = q
                        exc = f
                    else:
                        site.kids.append(mk("str", q, line, []))
                if bad != "":
                    break
                ok.append(a)
            subs: list[int] = []  # the names that are submodules, which run their code
            gone = len(x.kids)  # the first name that is neither bound by module p nor a submodule
            for j in range(len(x.kids) if x.s != "" and bad == "" and not builtin_module(p) else 0):
                # CPython's fromlist: each name module p does not bind is imported as its submodule
                # (one that is not found is passed over), then the names are bound
                xn = x.kids[j].kids[0].s[x.kids[j].kids[0].s.rfind(".") + 1 :]
                r = 2 if bad != "" or x.kids[j].s == "*" else self.binds_name(m, p, xn)
                if r == 1:
                    # (CPython's handler runs if x is not bound by then)
                    site.kind = "badimport"
                    site.s = f"cannot tell whether module '{p}' has bound '{xn}' when this optional import runs (it binds '{xn}' in a branch, deletes it, only annotates it, binds it in a function or by a star import, or its code is still running): not supported"
                    site.kids = []
                    return True
                if r == 2:
                    continue
                if self.modpath(p + "." + xn) == "":
                    gone = min(gone, j)
                    continue
                f = self.init_fails(p + "." + xn)
                if f != "":
                    bad = p + "." + xn
                    exc = f
                else:
                    subs.append(j)
                    site.kids.append(mk("str", p + "." + xn, line, []))
            for j in range(len(x.kids) if x.s != "" and bad == "" and builtin_module(p) else 0):
                # a name that Pystachy's builtin module lacks: as one that a module does not bind
                if x.kids[j].s != "*" and not builtin_has(p, x.kids[j].kids[0].s[len(p) + 1 :]):
                    gone = min(gone, j)
            if bad == "" and gone < len(x.kids):
                bad = p
                exc = "ImportError"
                named = x.kids[gone].kids[0].s[x.kids[gone].kids[0].s.rfind(".") + 1 :]
                ok = x.kids[:gone]
            elif bad != "" and x.s != "":
                ok = x.kids[:0]  # (a submodule's ImportError comes before any name is bound)
            if len(ok) == len(x.kids):
                run.append(x)
            elif len(ok) > 0:
                run.append(mk("import", x.s, x.line, ok))
            for j in subs:
                if j >= len(ok):
                    # a submodule that runs its code, though the statement does not bind it
                    sub = p + "." + x.kids[j].kids[0].s[x.kids[j].kids[0].s.rfind(".") + 1 :]
                    run.append(mk("import", "", line, [mk("alias", "", line, [mk("str", sub, line, []), mk("str", sub, line, [])])]))
        h = 0  # the handler that catches the exception
        for j in range(1, len(st.kids)):
            if st.kids[j].kind == "except" and h == 0:
                t = st.kids[j].kids[0]
                for e in t.kids if t.kind == "tuple" else [t]:
                    if e.s == "ImportError" or e.s == exc:
                        h = j
        missing = bad != "" and exc == "ModuleNotFoundError" and self.modpath(bad) == ""
        if bad != "" and not missing and named == "":
            site.s = bad
        if not scan:
            self.sites.append(site)
            self.sitem.append(m)
            self.siterest.append(mk("block", "", line, st.kids[0].kids[n:] if bad == "" else st.kids[0].kids[:0]))
        if bad == "" or h == 0:
            # every import succeeds, or the exception is not caught: the body runs (the failing
            # module's raise ends the program, as in CPython), then the else block
            out.extend(st.kids[0].kids)
            for e in st.kids[1:]:
                if e.kind == "block" and e.s == "else":
                    out.extend(e.kids)
            return True
        b = st.kids[h].kids[1]
        if st.kids[h].s != "" or may_end(b, True) or (missing and may_end(b, False)):
            # the handler needs the exception, or may end the program where the module is not found
            # (CPython may find it: a module of its standard library, or an installed package): the
            # module is required
            if named != "":
                msg = f"cannot import name '{named}' from '{bad}', and an except clause that re-raises or names the exception is not supported"
            elif missing:
                why = "names the exception (as " + short(st.kids[h].s) + ")" if st.kids[h].s != "" else "re-raises the exception" if may_end(b, True) else "may end the program"
                msg = f"module '{bad}' is not supported: it is not a builtin module and there is no {bad[bad.rfind('.') + 1 :]}.py on the module path; an optional import whose except clause {why} needs its module"
            else:
                msg = f"module '{bad}' raises {exc} as it initializes, and an except clause that re-raises or names the exception is not supported"
            out.append(mk("badimport", msg, line, []))
            return True
        out.extend(run)
        par = bad if named != "" else bad[: bad.rfind(".")] if missing and "." in bad else "" if missing else bad
        if par != "" and not builtin_module(par):
            # the code of the failing module's packages runs (and its own until its raise), binding nothing
            al = mk("alias", "", line, [mk("str", par, line, []), mk("str", par, line, [])])
            if not missing and named == "":
                al.kids.append(mk("guard", "", line, []))
            out.append(mk("import", "", line, [al]))
        out.extend(b.kids)
        return True

    def unbound_try(self, m: Mod, st: Node, before: list[Node], after: list[Node], out: list[Node]) -> bool:
        # a try that tests whether names are bound, a statement of module m's code (before: the
        # statements that run before it, where simplify() has decided them; after: those after
        # it), decided at compile time where nothing but the try itself binds them: no other
        # statement of m's code, no global statement of a function, no star import and, in a
        # package, no import of its submodule of that name. A try whose first statement reads, or
        # assigns, such a name (or a tuple or list of names among which it is) that is no builtin
        # of CPython 3.13 raises NameError before anything else of it runs (Python 2's basestring,
        # Windows' WindowsError): the first handler that catches it runs, unless it names it (as
        # e) or may re-raise it. But where the try binds the name (unicode = str in its handler),
        # another module may have assigned it through m first, if m imports a user module before
        # the try: then the try runs. A try whose statements only read builtins (or assign them to
        # names: text_type = str) raises nothing: its body runs, then its else block. Appends what
        # runs to out; False if st is no such try, or has a finally clause
        if st.kind != "try" or st.s != "" or self.incls or len(st.kids[0].kids) == 0:
            return False
        first = st.kids[0].kids[0]
        e = first.kids[-1] if first.kind == "assign" or first.kind == "expr" else first
        if e.kind != "name" and e.kind != "tuple" and e.kind != "list":
            return False
        for h in st.kids[1:]:
            if h.kind == "block" and h.s == "finally":
                return False
        other: dict[str, bool] = {}
        rest = before + after
        binds(rest, other, True)
        for x in rest:
            bound_in(x, other)
        fn_globals(mk("block", "", st.line, rest), other)
        fn_globals(st, other)
        if "*" in other:
            return False
        unbound: list[str] = []  # (the first statement's names that are surely not bound)
        pure = True  # (each statement only reads builtins, or assigns them to names)
        kept: list[Node] = []  # (and those that assign)
        for j in range(len(st.kids[0].kids)):
            x = st.kids[0].kids[j]
            e = x.kids[-1] if x.kind == "assign" or x.kind == "expr" else x
            names = [e] if e.kind == "name" else e.kids if e.kind == "tuple" or e.kind == "list" else e.kids[:0]
            pure = pure and len(names) > 0
            for t in x.kids[:-1] if x.kind == "assign" else x.kids[:0]:
                pure = pure and t.kind == "name"
            for nm in names:
                if nm.kind != "name" and j == 0:
                    return False
                pure = pure and nm.kind == "name" and nm.s in PYBUILTINS and nm.s not in other
                if j == 0 and not (nm.s in PYBUILTINS or nm.s in MODNAMES or nm.s.startswith("__") or nm.s in other):
                    if m.pdir == "" or self.modpath(m.name + "." + nm.s) == "":
                        unbound.append(nm.s)
            if x.kind == "assign":
                kept.append(x)
        if pure:
            out.extend(kept)  # (a read of a builtin does nothing)
            for h in st.kids[1:]:
                if h.kind == "block" and h.s == "else":
                    out.extend(h.kids)
            return True
        own: dict[str, bool] = {}
        binds([st], own, True)
        fn_globals(st, own)
        if m.name != "" and imports_user(mk("block", "", st.line, before)):
            unbound = [u for u in unbound if u not in own]
        if len(unbound) == 0:
            return False
        for h in st.kids[1:]:
            catch = False
            for x in (h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]]) if h.kind == "except" else h.kids[:0]:
                if x.kind == "omit" or (x.kind == "name" and x.s in ["NameError", "Exception", "BaseException"] and x.s not in m.rebound):
                    catch = True
                elif x.kind != "name" or x.s not in PYBUILTINS or x.s in m.rebound:
                    return False  # (a class that may be NameError's)
            if catch and (h.s != "" or may_end(h.kids[1], True)):
                return False  # (as e, or a bare raise: the handler needs the exception)
            if catch:
                out.extend(h.kids[1].kids)
                return True
        return False

    def binds_name(self, m: Mod, p: str, x: str) -> int:
        # has module p's code bound x itself when a from-import in module m takes x from it: 2 surely,
        # 1 maybe (in a branch, by a function's global statement or a star import, ...), 0 not. A
        # module not loaded yet runs its code to its end (what static_if() and optional() leave of
        # it); one whose code is running (a circular import, or p is m) has run it up to that import
        if x == "__doc__":
            return 2  # (every module has one: Mod.doc)
        path = self.mods[p].path if p in self.mods else self.modpath(p)
        if not path.endswith(".py"):
            return 0  # (a namespace package binds nothing)
        t = self.mods[p] if p in self.mods and p != m.name else Mod(p, path, path[:-12] if path.endswith("/__init__.py") else "")
        maybe = t.maybe
        if p == m.name:
            # (what the statements before it bind, found once for all the optional imports in them)
            end = self.pos if self.pos >= 0 else len(m.body.kids)
            if self.ownkids is not m.body.kids or self.ownpos > end:
                self.ownkids = m.body.kids
                self.ownpos = 0
                self.ownsure = {}
                self.ownmaybe = {}
            for st in m.body.kids[self.ownpos : end]:
                surely_binds(st, self.ownsure, self.ownsure)
                for nm in rebound([st], True):
                    self.ownmaybe[nm] = True
            self.ownpos = end
            t.sure = self.ownsure
            maybe = self.ownmaybe
        elif p not in self.mods:
            if path not in self.rawbound:
                self.scan(t)
            t.sure = self.rawsure[path]
            maybe = self.rawbound[path]
        elif t.done or self.pos < 0:
            maybe = {x: True} if x in t.kinds else {}  # (its code has run to its end, or may have)
        return 2 if x in t.sure else 1 if x in maybe or x in t.fnglobal or "*" in maybe else 0

    def scan(self, t: Mod) -> None:
        # what module t's code binds, not loaded yet: surely (at its top level), and maybe
        self.rawbound[t.path] = {"*": True}  # (while it is scanned: a module that imports t back cannot tell)
        self.rawsure[t.path] = {}
        t.body = self.parse(t.path)
        self.prescan(t)
        pos = self.pos
        fs = self.fs
        incls = self.incls
        self.fs = Mod("", "", "")
        self.incls = False
        kept: list[Node] = []
        sure: dict[str, bool] = {}
        self.folded(t, t.body.kids, kept, sure, True)
        self.pos = pos
        self.fs = fs
        self.incls = incls
        self.rawbound[t.path] = rebound(kept, True)
        self.rawsure[t.path] = sure

    def folded(self, t: Mod, body: list[Node], kept: list[Node], sure: dict[str, bool], top: bool) -> None:
        # the statements of module t's code (body) that run where static_if() and optional() decide
        # (kept), and the names they surely bind
        for i in range(len(body)):
            if top:
                self.pos = i
            run: list[Node] = []
            if self.static_if(t, body[i], {}, run) or self.optional(t, body[i], run, True) or (top and self.unbound_try(t, body[i], kept, body[i + 1 :], run)):
                self.folded(t, run, kept, sure, False)
            else:
                kept.append(body[i])
                surely_binds(body[i], sure, sure)

    def binds_surely(self, p: str, x: str) -> bool:
        # does module p's code bind x at its top level for sure (not only in an if, try or loop)
        path = self.mods[p].path if p in self.mods else self.modpath(p)
        if not path.endswith(".py"):
            return False
        bound: dict[str, bool] = {}
        for st in self.mods[p].body.kids if p in self.mods else self.parse(path).kids:
            surely_binds(st, bound, bound)
        return x in bound

    def init_fails(self, name: str) -> str:
        # the exception module name's code raises at its top level for sure (init_raise()), or ""
        if name in self.mods:
            return self.mods[name].fails
        p = self.modpath(name)
        if name in self.failc or name in self.scanning or not p.endswith(".py"):
            # (a module whose code imports it back finds it half run; a namespace package has no code)
            return self.failc.get(name, "")
        t = Mod(name, p, p[:-12] if p.endswith("/__init__.py") else "")
        t.body = self.parse(p)
        self.prescan(t)
        r: list[Node] = []
        pos = self.pos
        fs = self.fs
        incls = self.incls
        self.fs = Mod("", "", "")  # (t's code is not in the function or class body simplify() may be in)
        self.incls = False
        self.scanning[name] = True
        self.init_raise(t, t.body.kids, r, True)
        del self.scanning[name]
        self.pos = pos
        self.fs = fs
        self.incls = incls
        self.failc[name] = import_error(r[0].kids[0]) if len(r) > 0 else ""
        return self.failc[name]

    def init_raise(self, m: Mod, body: list[Node], out: list[Node], top: bool) -> bool:
        # the raise of ImportError (or ModuleNotFoundError) that module m's code reaches for sure at its
        # top level (body, if top), where simplify() leaves it, goes to out; True if it is found
        for i in range(len(body)):
            st = body[i]
            if top:
                self.pos = i
            run: list[Node] = []
            if st.kind == "raise" and len(st.kids) > 0 and import_error(st.kids[0]) != "":
                out.append(st)
                return True
            if (self.static_if(m, st, {}, run) or self.optional(m, st, run, True) or (top and self.unbound_try(m, st, body[:i], body[i + 1 :], run))) and self.init_raise(m, run, out, False):
                return True
        return False

    def guarded(self) -> None:
        # an optional import is decided at compile time, so the code that runs in its try must not
        # raise ImportError in another way: neither what the modules it imports run at import (and
        # the modules they import) nor the statements after the imports, by a raise of their own or
        # by a call, if a function of the program may raise ImportError. The site (a pass statement
        # where the try was) becomes an error where it is compiled.
        back: dict[str, str] = {}  # what failing() found, by the failing module and the importing one
        for i in range(len(self.sites)):
            s = self.sites[i]
            m = self.sitem[i]
            seen: dict[str, bool] = {}
            why = ""
            for x in s.kids:
                if x.s in self.mods and why == "":
                    why = self.why(self.raises(self.mods[x.s], "", seen), f"the code of module '{x.s}'")
            key = s.s + " " + m.name
            if s.s in self.mods and why == "" and key not in back:
                back[key] = self.failing(self.mods[s.s], m)
            if s.s in self.mods and why == "":
                why = back[key]
            if why == "":
                why = self.why(self.raises_in(self.siterest[i], m, False, seen), "the code that runs in the try")
            s.kids = []
            if why != "":
                s.kind = "badimport"
                s.s = why

    def failing(self, t: Mod, m: Mod) -> str:
        # what keeps an optional import in module m of module t, whose code raises ImportError at its
        # top level, from being decided: t's code may raise it otherwise, or import m back (CPython's
        # import then finds m half run, and succeeds); the message, or ""
        why = self.why(self.raises(t, t.name, {}), f"the code of module '{t.name}', besides its top-level raise,")
        if why == "" and self.imports_mod(t.body, m.name, {}, False):
            return f"module '{t.name}' imports this module as its code runs, before that raises ImportError: an optional import of it here is not supported"
        if why == "" and self.imports_mod(t.body, m.name, {}, True) and self.raises_in(t.body, t, True, {}) > 0:
            return f"module '{t.name}' may import this module as its code runs (through a call), before that raises ImportError: an optional import of it here is not supported"
        return why

    def why(self, r: int, what: str) -> str:
        # the message for code that may raise ImportError (raises_in() found r), or ""
        tail = "which the except clause would catch: not supported (Pystachy decides optional imports at compile time)"
        if r == 2:
            return f"{what} may raise ImportError, {tail}"
        for t in self.order if r == 1 and self.fn == "?" else self.order[:0]:
            if self.fn == "?" or self.fn == "":
                self.fn = self.fn_raises(t, t.body)
        if r == 1 and self.fn != "":
            return f"{what} may raise ImportError through a call (function {self.fn} may raise it), {tail}"
        return ""

    def fn_raises(self, t: Mod, n: Node) -> str:
        # the first function or method in code n of module t that may raise ImportError, by a raise of
        # its own or by an import of a module whose code may: its name, or ""
        for k in n.kids:
            if k.kind == "def" and self.raises_in(k.kids[2], t, False, {}) == 2:
                return f"{t.name + '.' if t.name != '' else ''}{k.s}()"
            r = self.fn_raises(t, k) if k.kind != "def" else ""
            if r != "":
                return r
        return ""

    def raises(self, m: Mod, ok: str, seen: dict[str, bool]) -> int:
        # may module m's code, as it runs at import, raise ImportError (other than the top-level raise
        # of module ok, which an optional import guards)? As raises_in()
        if m.name != ok and m.name in self.rmemo:
            return self.rmemo[m.name]
        if m.name in seen:
            self.rcyc = True  # (its code runs already, or was counted: a result that includes it is not its own)
            return 0
        top = len(seen) == 0  # (then what it finds is all its code may run, cycles or not)
        seen[m.name] = True
        cyc = self.rcyc
        self.rcyc = False
        r = self.raises_in(m.body, m, m.name == ok, seen)
        if m.name != ok and (top or not self.rcyc):
            self.rmemo[m.name] = r
        self.rcyc = self.rcyc or cyc
        return r

    def raises_in(self, n: Node, m: Mod, ok: bool, seen: dict[str, bool]) -> int:
        # may code n of module m raise ImportError as it runs (not the bodies of the functions it
        # defines)? 2 if by a raise of its own or of a module it imports, 1 if it may call a
        # function or method of the program (any call but of a builtin with constant arguments, an
        # operator, a truth test, ...), else 0
        k = n.kind
        if k == "raise" and len(n.kids) > 0 and import_error(n.kids[0]) != "" and not (ok and n.s == "init"):
            return 2
        if k == "call" and self.plain_call(n, m):
            return 0
        if k == "assign" and n.s == "from" and n.kids[-1].kind == "name" and owner(n.kids[-1].s) in self.mods and not self.binds_surely(owner(n.kids[-1].s), short(n.kids[-1].s)):
            return 2  # (from m import x, where m's code may leave x unbound: CPython raises ImportError)
        r = 0 if k in NOCALL else 1
        if k == "uimport":
            for x in n.kids:
                if x.kind == "str" and x.s in self.mods:
                    r = max(r, self.raises(self.mods[x.s], "", seen))
        own = k == "try" and catches_import(n) and not may_end(n, True)  # (a try whose clauses catch ImportError, and do not re-raise it)
        for i in range(len(n.kids)):
            if (k == "def" and (i == 1 or i == 2)) or (k == "annassign" and i == 1) or (k.endswith("param") and i == 0) or (own and i == 0):
                continue  # (a def runs its parameters' defaults and decorators, not its body; annotations call nothing)
            if r < 2:
                r = max(r, self.raises_in(n.kids[i], m, ok, seen))
        return r

    def plain_call(self, n: Node, m: Mod) -> bool:
        # a call of a builtin (that module m does not rebind) with constant arguments: print("loaded")
        f = n.kids[0]
        if f.kind != "name" or f.s not in PYBUILTINS or f.s in m.kinds:
            return False
        for a in n.kids[1:]:
            v = a.kids[0] if a.kind == "kw" else a
            if v.kind != "str" and v.kind != "int" and v.kind != "float" and v.kind != "None" and v.kind != "True" and v.kind != "False":
                return False
        return True

    def imports_mod(self, n: Node, name: str, seen: dict[str, bool], fns: bool) -> bool:
        # does code n import module name, itself or through the modules it imports (with fns, also
        # in the functions they define)?
        if n.kind == "uimport":
            for x in n.kids:
                if x.s == name:
                    return True
                if x.s in self.mods and x.s not in seen:
                    seen[x.s] = True
                    if self.imports_mod(self.mods[x.s].body, name, seen, fns):
                        return True
        for k in n.kids if fns or n.kind != "def" else n.kids[:0]:
            if self.imports_mod(k, name, seen, fns):
                return True
        return False

    def submodules(self) -> None:
        # a package that binds a name x itself (util = "a string") while the program imports its
        # submodule x too: the first import of the submodule rebinds the package's x to it, at a time
        # Pystachy cannot tell, unless the package's own code imports the submodule before it binds x
        # (from .parse import parse). Such an x is ambiguous (Mod.amb): reading it from another module
        # (qmod(), take()) or in the package's functions (qexpr()) is an error where it is compiled
        for t in self.order:
            for x in t.kinds:
                sub = t.name + "." + x
                if t.pdir != "" and sub in self.mods and t.kinds[x] != "m:" + sub and not self.own_first(t, x):
                    t.amb[x] = self.imports_mod(t.body, sub, {}, True)
        for i in range(len(self.taken)):
            n = self.taken[i]
            t = self.mods[n.kids[0].s]
            x = n.kids[1].s
            if n.kind == "takemid" and not (x in t.amb and not t.amb[x] and x not in t.fnglobal):
                # (attribute x of t is the submodule only once an import of it has rebound t's own x,
                # as for the last step, below; else CPython raises ImportError)
                n.kids[2].kind = "badimport"
                n.kids[2].s = self.ambiguous(t.name, x) if x in t.amb else f"import {n.kids[3].s} as {n.s}: '{t.name}.{x}' is the package's own '{x}', not its submodule (not supported: CPython raises ImportError)"
            elif n.kind != "takemid" and x in t.amb:
                # (import t.x as y runs the submodule's code after t's, so t's x is the submodule from
                # then on, unless the submodule's code may run within t's or a function of t rebinds x)
                sure = n.kind == "takesub" and not t.amb[x] and x not in t.fnglobal
                msg = self.ambiguous(t.name, x)
                if len(n.kids) > 2:
                    n.kids[2].kind = "pass" if sure else "badimport"  # (the copy of a variable)
                    n.kids[2].s = msg
                    n.kids[2].kids = []
                self.takek[i][n.s] = "m:" + t.name + "." + x if sure else "x:" + msg
        for i in range(len(self.stars)):
            # from t import * without __all__ binds the public submodules of t that have been imported
            # by then too: one t's own code imports for sure, but another only where its import may
            # have run (an error where it is read)
            t = self.mods[self.stars[i].kids[0].s]
            m = self.starm[i]
            for sub in self.mods:
                x = sub[len(t.name) + 1 :]
                if sub.startswith(t.name + ".") and "." not in x and not x.startswith("_") and x not in t.kinds:
                    msg = f"'from {t.name} import *' binds '{x}' to the submodule '{sub}' only if an import of it has run before, and Pystachy cannot tell whether one has (not supported)"
                    sure = False
                    for st in t.body.kids:
                        for y in st.kids if st.kind == "uimport" else st.kids[:0]:
                            sure = sure or y.s == sub
                    k = m.kinds.get(x, "m:" + sub)
                    if sure and k == "m:" + sub:
                        m.kinds[x] = "m:" + sub
                    elif sure:
                        # (the module binds x itself too)
                        if k == "v":
                            msg = f"'{x}' is bound both as a variable and by an import (not supported)"
                        elif k == "f" or k == "c":
                            msg = f"'{x}' is bound both by an import and by a def or class (not supported)"
                        else:
                            msg = f"'{x}' is bound by two imports, to different modules, functions or classes (not supported)"
                        fail(msg, self.stars[i].line)
                    elif x in m.kinds:
                        fail(msg, self.stars[i].line)
                    else:
                        m.kinds[x] = "x:" + msg

    def own_first(self, t: Mod, x: str) -> bool:
        # does package t's top-level code import its submodule x before anything in it binds x, while
        # no function rebinds x? Then x is t's own binding once t's code has run
        if x in t.fnglobal:
            return False
        for st in t.body.kids:
            for y in st.kids if st.kind == "uimport" else st.kids[:0]:
                if y.s == t.name + "." + x:
                    return True
            names: dict[str, bool] = {}
            binds([st], names, True)
            if x in names:
                return False
        return False

    def ambiguous(self, p: str, x: str) -> str:
        return f"'{p}.{x}' is the package's own '{x}' until the program's first import of its submodule '{p}.{x}' replaces it, and Pystachy cannot tell which of the two this is (not supported)"

    def decide(self, m: Mod, e: Node, scope: dict[str, bool], pre: list[Node]) -> int:
        # an if condition, or a conditional expression's test, that tests the system Pystachy
        # compiles for (platform_test(); in module code also a name its module assigns such a test
        # once, platform_flags()), the version
        # (a comparison of sys.version_info, a slice, an item or an attribute of it with a
        # literal: version_cmp()), TYPE_CHECKING, an
        # imported module's __name__ == "__main__" or, in module code outside class bodies, False and
        # 0 (false), also under not/and/or: 1 or 0, after appending to pre what still runs for the
        # other operands, in CPython's order ("if x: pass" for an operand x that is evaluated and
        # tested); -1 if e is undecided
        if e.kind == "unary" and e.s == "not":
            r = self.decide(m, e.kids[0], scope, pre)
            return 1 - r if r >= 0 else -1
        if e.kind == "boolop":
            stop = 0 if e.s == "and" else 1  # the value that decides e on its own
            a: list[Node] = []
            b: list[Node] = []
            ra = self.decide(m, e.kids[0], scope, a)
            rb = self.decide(m, e.kids[1], scope, b) if ra != stop else -1
            if ra == stop or (ra >= 0 and rb >= 0):
                pre.extend(a)
                pre.extend(b)
                return ra if ra == stop else rb
            if ra < 0 and rb == stop:
                # x and False, x or True: x runs and is tested, then what the right operand runs where x
                # does not decide
                run = mk("block", "", e.line, b if len(b) > 0 else [mk("pass", "", e.line, [])])
                skip = mk("block", "", e.line, [])
                pre.append(mk("if", "", e.line, [e.kids[0], run if stop == 0 else skip, skip if stop == 0 else run]))
                return stop
            return -1
        if e.kind == "attr" and e.s == "TYPE_CHECKING" and e.kids[0].kind == "name" and self.special(m, e.kids[0].s, scope) == "typing":
            return 0
        if e.kind == "name" and self.special(m, e.s, scope) == "typing.TYPE_CHECKING":
            return 0
        if e.kind == "name" and e.s == "TYPE_CHECKING" and not self.incls and m.falseat >= 0 and m.falseat < self.pos:
            return 0  # (module code after TYPE_CHECKING = False, outside class bodies: false_flag())
        if (e.kind == "False" or (e.kind == "int" and e.s.strip("0") == "")) and self.pos >= 0 and not self.incls:
            # (in module code: in a function, what the branch binds is still local; in a class body, a
            # global statement in it still holds for the whole body)
            return 0
        if (m.name != "" or self.ext != "") and is_main_guard(e) and "__name__" not in scope and "__name__" not in m.rebound:
            return 0  # (in an imported module, or an extension module's)
        if e.kind == "name" and e.s in m.flagat and m.flagat[e.s] < self.pos and not self.incls:
            return m.flagval[e.s]  # (in module code after its name = <a test of the platform>: platform_flags())
        r = self.platform_test(m, e, scope)
        if r >= 0:
            return r
        if e.kind == "cmp" and e.s in ["<", "<=", ">", ">=", "==", "!="] and (self.version(m, e.kids[0], scope, True) != [] or self.version(m, e.kids[1], scope, True) != []):
            return self.version_cmp(e.s, self.version(m, e.kids[0], scope, False), self.version(m, e.kids[1], scope, False))
        return -1

    def platform_test(self, m: Mod, e: Node, scope: dict[str, bool]) -> int:
        # a test of the system Pystachy compiles for, which CPython makes as the code runs, with what
        # the runtime reports: sys.platform == or != a literal str (PLATFORM), in or not in a tuple
        # or list of those, sys.platform.startswith() of one or a tuple of those, os.name == or != a
        # literal str ("posix") and sys.implementation.name == or != one ("pystachy"): 1 or 0; -1
        # for anything else
        if e.kind == "cmp" and (e.s == "in" or e.s == "not in") and (e.kids[1].kind == "tuple" or e.kids[1].kind == "list") and self.is_platform(m, e.kids[0], scope):
            r = 0
            for x in e.kids[1].kids:
                if x.kind != "str":
                    return -1
                if x.s == PLATFORM:
                    r = 1
            return r if e.s == "in" else 1 - r
        if e.kind == "cmp" and (e.s == "==" or e.s == "!=") and e.kids[1].kind == "str" and e.kids[0].kind == "attr":
            a = e.kids[0]
            r = -1
            if self.is_platform(m, a, scope):
                r = 1 if e.kids[1].s == PLATFORM else 0
            elif a.s == "name" and a.kids[0].kind == "name" and self.special(m, a.kids[0].s, scope) == "os":
                r = 1 if e.kids[1].s == OSCONST["os.name"] else 0
            elif a.s == "name" and a.kids[0].kind == "attr" and a.kids[0].s == "implementation" and a.kids[0].kids[0].kind == "name" and self.special(m, a.kids[0].kids[0].s, scope) == "sys":
                r = 1 if e.kids[1].s == IMPLEMENTATION else 0
            return r if r < 0 or e.s == "==" else 1 - r
        if e.kind == "call" and len(e.kids) == 2 and (e.kids[1].kind == "str" or e.kids[1].kind == "tuple") and e.kids[0].kind == "attr" and e.kids[0].s == "startswith" and self.is_platform(m, e.kids[0].kids[0], scope):
            r = 0
            for x in e.kids[1].kids if e.kids[1].kind == "tuple" else [e.kids[1]]:
                if x.kind != "str":
                    return -1
                if PLATFORM.startswith(x.s):
                    r = 1
            return r
        return -1

    def is_platform(self, m: Mod, e: Node, scope: dict[str, bool]) -> bool:
        # is e sys.platform, of the module sys (special())
        return e.kind == "attr" and e.s == "platform" and e.kids[0].kind == "name" and self.special(m, e.kids[0].s, scope) == "sys"

    def platform_value(self, m: Mod, e: Node) -> int:
        # the value of e, in module m's top-level code, where it is built only from the tests that
        # platform_test() decides, with not, and, or (a bool, as they are): 1 or 0; else -1
        if e.kind == "unary" and e.s == "not":
            r = self.platform_value(m, e.kids[0])
            return 1 - r if r >= 0 else -1
        if e.kind == "boolop":
            a = self.platform_value(m, e.kids[0])
            b = self.platform_value(m, e.kids[1])
            if a < 0 or b < 0:
                return -1
            return min(a, b) if e.s == "and" else max(a, b)
        return self.platform_test(m, e, {})

    def platform_flags(self, m: Mod) -> None:
        # module m's top-level name = <a test of the platform> (platform_value()), the only statement
        # that binds name (sole_binding()), as _MS_WINDOWS = (sys.platform == 'win32'): its tests in
        # module code after it, outside class bodies, are decided (decide()); simplify() makes it
        # assign the literal, as which a store through the module may assign only that (Gen.store_name())
        m.flagat = {}
        m.flagval = {}
        body = m.body.kids
        pos = self.pos
        fs = self.fs
        self.fs = Mod("", "", "")
        for i in range(len(body)):
            st = body[i]
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s != "TYPE_CHECKING" and st.kids[0].s not in m.flagat:
                self.pos = i
                r = self.platform_value(m, st.kids[1])
                if r >= 0 and sole_binding(body, i, st.kids[0].s):
                    m.flagat[st.kids[0].s] = i
                    m.flagval[st.kids[0].s] = r
        self.pos = pos
        self.fs = fs

    def version(self, m: Mod, e: Node, scope: dict[str, bool], own: bool) -> list[str]:
        # the constant that e is, if it is sys.version_info, a slice, an item or an attribute of it
        # (also, unless own, a literal int or str, or a tuple of those): its items, ints in decimal
        # and strs after a "'", after a "(" for a tuple; [] for anything else
        v = ["("]
        for c in VERSIONINFO.values():
            v.append(c[:-1] if c.startswith("'") else c)
        if self.is_version(m, e, scope):
            return v
        b = e.kids[0] if e.kind == "attr" or e.kind == "index" or e.kind == "slice" else e
        if self.is_version(m, b, scope):
            fields = ["major", "minor", "micro", "releaselevel", "serial"]
            if e.kind == "attr" and e.s in fields:
                return [v[fields.index(e.s) + 1]]
            if e.kind == "attr":
                return []
            ix = [self.version(m, x, scope, False) if x.kind != "omit" else ["?"] for x in e.kids[1:]]
            for bd in ix:
                if len(bd) != 1 or bd[0].startswith("'"):
                    return []  # (a bound that is no int literal)
            if e.kind == "index" and -5 <= int(ix[0][0]) < 5:
                i = int(ix[0][0])
                return [v[i + 1 if i >= 0 else i + 6]]
            if e.kind == "index":
                return []
            if len(ix) == 2:
                return ["("] + v[1:][int(ix[0][0]) if ix[0][0] != "?" else 0 : int(ix[1][0]) if ix[1][0] != "?" else 5]
            return []
        if own:
            return []
        if e.kind == "int" and e.s.isdigit() and int_fits(e.s):
            return [str(int(e.s))]
        if e.kind == "unary" and e.s == "-" and e.kids[0].kind == "int" and e.kids[0].s.isdigit() and int_fits(e.kids[0].s):
            return [str(-int(e.kids[0].s))]
        if e.kind == "str":
            return ["'" + e.s]
        if e.kind != "tuple":
            return []
        out = ["("]
        for x in e.kids:
            item = self.version(m, x, scope, False)
            if len(item) != 1:
                return []
            out.append(item[0])
        return out

    def is_version(self, m: Mod, e: Node, scope: dict[str, bool]) -> bool:
        # is e sys.version_info, where sys is the builtin module (special())
        return e.kind == "attr" and e.s == "version_info" and e.kids[0].kind == "name" and self.special(m, e.kids[0].s, scope) == "sys"

    def version_cmp(self, op: str, a: list[str], b: list[str]) -> int:
        # a op b, of two of version()'s constants: 1 or 0, as Python compares two tuples or two
        # items; -1 where they are not both (or a comparison would raise TypeError, as of an int
        # and a str), which is decided where it runs
        if len(a) == 0 or len(b) == 0 or (a[0] == "(") != (b[0] == "("):
            return -1
        x = a[1:] if a[0] == "(" else a
        y = b[1:] if b[0] == "(" else b
        i = 0
        while i < len(x) and i < len(y) and x[i] == y[i]:
            i += 1
        c = len(x) - len(y)
        if i < len(x) and i < len(y):
            if x[i].startswith("'") != y[i].startswith("'"):
                return -1 if op != "==" and op != "!=" else 1 if op == "!=" else 0
            c = (1 if x[i] > y[i] else -1) if x[i].startswith("'") else 1 if int(x[i]) > int(y[i]) else -1
        r = c < 0 if op == "<" else c <= 0 if op == "<=" else c > 0 if op == ">" else c >= 0 if op == ">=" else c == 0 if op == "==" else c != 0
        return 1 if r else 0

    def special(self, m: Mod, name: str, scope: dict[str, bool]) -> str:
        # what name is in module m's code, where scope (the names of the function or class the code
        # is in) does not hide it, if m binds it only by imports special_import() recognizes, one of
        # them at its top level before the code (self.pos) if that is top-level code: a builtin module
        # (import sys, import os as _os: "sys", "os") or "typing.TYPE_CHECKING"; else "". In a
        # function that binds name only by such imports of its own, what they bind, where one of
        # them has surely run (self.fsure)
        if name in self.fs.spec and name not in self.fs.rebound:
            return self.fs.spec[name] if name in self.fsure else ""
        if name in scope or name in m.rebound or name not in m.specat:
            return ""
        return m.spec[name] if self.pos < 0 or m.specat[name] < self.pos else ""

    def prescan(self, m: Mod) -> None:
        # what simplify() needs to know of m's code first: the names it binds other than by the
        # imports special_import() recognizes (rebound()), and the names those imports bind
        # (Mod.spec). A star import that binds such a name otherwise is an error (bind()). And its
        # TYPE_CHECKING = False, if that is a constant (false_flag())
        m.rebound = rebound(m.body.kids, False)
        specials(m, m.body.kids, -1)
        m.falseat = false_flag(m.body.kids)
        self.platform_flags(m)

    def imports(self, m: Mod, blk: Node, infn: bool) -> None:
        # load the user modules that the import statements in blk name, and rewrite those
        out: list[Node] = []
        added: list[str] = []  # (what blk surely binds holds only within it)
        for st in blk.kids:
            if blk is m.body:
                m.at = st.line
            if st.kind == "import" and infn and m.name != "":
                self.later.append(st)
                self.laterm.append(m)
                self.laterb.append(blk)
                self.laterd.append(self.curdef)
                self.latert.append(self.intry)
                out.append(st)
            elif st.kind == "import":
                self.import_stmt(m, st, infn, out)
            else:
                out.append(st)
                saved = self.curdef
                if st.kind == "def":
                    self.curdef = str(st.line)
                    self.fks[self.curdef] = {}
                    self.fgl[self.curdef] = {}
                    globals_in(st.kids[2].kids, self.fgl[self.curdef])
                elif not infn and (st.kind == "for" or st.kind == "while"):
                    binds([st], self.maybe, True, m.name if m.pdir != "" else "")  # (an earlier pass of the loop may have run its body)
                intry = self.intry
                optry = self.optry
                self.intry = 0 if st.kind == "def" else intry + 1 if st.kind == "try" else intry
                for kid in st.kids[0].kids if st.kind == "subclass" else st.kids:
                    self.optry = optry and st.kind != "def" or (st.kind == "try" and kid is st.kids[0] and catches_import(st))
                    if kid.kind == "block":
                        self.imports(m, kid, infn or st.kind == "def")
                    elif kid.kind == "except":
                        self.imports(m, kid.kids[1], infn)
                self.intry = intry
                self.optry = optry
                self.curdef = saved
            if not infn:
                binds([st], self.maybe, True, m.name if m.pdir != "" else "", False)  # (imports() did its blocks)
                now: dict[str, bool] = {}
                surely_binds(st, now, self.sure, False)  # (and so an elif chain is not walked again for each elif)
                for nm in now:
                    if nm not in self.sure:
                        self.sure[nm] = True
                        added.append(nm)
        if blk is not m.body:
            for nm in added:
                if nm in self.sure:
                    del self.sure[nm]
        blk.kids = out

    def bind(self, m: Mod, name: str, k: str, infn: bool, line: int) -> None:
        # what an import binds name to; in a function, for that function only. One binding stands for
        # all the code, so a name that an earlier import bound to another module, function or class
        # is an error (in a function, where it is compiled)
        ks = self.fks[self.curdef] if infn else m.kinds
        old = ks.get(name, k)
        if old != k and (old.startswith("m:") or old.startswith("b:") or old.startswith("a:") or old.startswith("t:")) and not k.startswith("x:"):
            k = f"x:'{name}' is bound by two imports, to different modules, functions or classes (not supported)"
            if not infn:
                fail(k[2:], line)
        if infn and name not in ks:
            self.fkline[f"{self.curdef} {name}"] = line
        ks[name] = k

    def import_stmt(self, m: Mod, st: Node, infn: bool, out: list[Node]) -> None:
        # one import statement becomes: an import node with its builtin modules (for code
        # generation), a uimport node with the user modules to initialize (each package before
        # its submodules), and for every variable taken with from-import an assignment of its
        # current value, as CPython binds it (marked "from"). A name that has a flag (import_binds())
        # is bound where CPython binds it, by a "bound" node that sets the flag: in a plain import
        # once the code of its own modules has run (the uimport is split there), in a from-import
        # once that of all of them has, in the order of its names, among the copies
        line = st.line
        keep = mk("import", st.s, line, [])
        inits = mk("uimport", "", line, [])
        copies: list[Node] = []
        names: list[str] = []
        took: list[str] = []  # (the names a from-import binds in order: "" a variable it copies)
        # (a plain import: where each alias's modules start in inits, where its copies start, and
        # the flag of the name it binds; then those of the names a from-import binds)
        at: list[int] = []
        cat: list[int] = []
        flags: list[str] = []
        checks: list[str] = []  # each from-imported alias must exist in its source module too
        for a in st.kids if infn else st.kids[:0]:
            same = "b:" + a.kids[0].s if builtin_import(st, a) else "m:" + a.kids[0].s if st.s == "" and builtin_module(a.kids[1].s) else ""
            if a.s in self.fgl.get(self.curdef, {}) and (same == "" or m.kinds.get(a.s, "") != same):
                # (CPython binds the module's global, which then names one module or another; but
                # for a builtin module, or the package of one (import collections.abc), that the
                # module's code has bound it to already)
                out.append(mk("badimport", f"an import of '{a.s}' in a function that declares it global is not supported", line, []))
                return
        for a in st.kids:
            at.append(len(inits.kids))
            cat.append(len(copies))
            flags.append("")
            path = a.kids[1].s
            if path == "typing_extensions":
                # the typing backport: its names are typing's (those typing has)
                path = "typing"
                a.kids[1].s = path
                a.kids[0].s = "typing" + a.kids[0].s[17:]
            if st.s.startswith("from."):
                path = self.relative(m, st.s, path, line)
            elif builtin_module(path) and not builtin_import(st, a):
                # import collections.abc binds the package collections, a Python module whose code
                # runs; it binds abc itself, as CPython's does
                path = a.kids[0].s
            elif builtin_module(path):
                if path == TYPESMOD and (len(self.dirs) == 0 or m.path != self.dirs[-1] + "/types.py"):
                    fail(f"module '{TYPESMOD}' is not supported: it is Pystachy's own, which its types module imports (import types)", line)
                if path == IOMOD and (len(self.dirs) == 0 or m.path != self.dirs[-1] + "/io.py"):
                    fail(f"module '{IOMOD}' is not supported: it is Pystachy's own, which its io module imports (import io)", line)
                if not infn and m.kinds.get(a.s, "") == "v":
                    fail(f"'{a.s}' is bound both as a variable and as a function, class or import (not supported)", line)
                if a.s == "*":
                    fail(f"'from {path} import *' is not supported", line)
                if a.kids[0].s in ("ffi.track", "ffi.untrack", "ffi.collected") and not self.in_lib(m.path):
                    fail(f"cannot import name '{a.kids[0].s[4:]}' from 'ffi': it is internal to Pystachy's lib/pyobj.py", line)
                self.bind(m, a.s, "b:" + a.kids[0].s, infn, line)
                if not infn and a.kids[0].s.startswith("builtins.") and is_excname(a.kids[0].s[9:]):
                    continue  # (a builtin exception class, which qname() names itself)
                keep.kids.append(a)
                if not infn and a.kids[0].s == "builtins." + a.s:
                    continue  # the same builtin is available before the import too
                if st.s == "":
                    flags[-1] = self.import_binds(m, a.s, infn)
                else:
                    took.append(a.s)
                    checks.append("")
                continue
            if infn and not builtin_module(path) and self.modpath(path) == "":
                # a module that cannot be found, imported by a function: an error only where the
                # function is compiled, as CPython's ImportError comes only where it runs
                msg = f"module '{path}' is not supported: it is not a builtin module and there is no {path[path.rfind('.') + 1 :]}.py on the module path"
                out.append(mk("badimport", msg, line, []))
                self.bind(m, a.s, "x:" + msg, infn, line)
                continue
            src = self.find(path, line)
            self.chain(path, inits)
            if a.s == "":
                # an import that fails in an optional import (optional()): its packages' code runs (and
                # the module's own until its raise, guarded), and it binds nothing
                if len(a.kids) > 2:
                    inits.kids[-1].kind = "guard"
                continue
            if st.s == "" and "." in a.kids[0].s:
                # import a.b.c as x binds x to attribute c of a.b, as from a.b import c as x does: the
                # submodule, unless a.b binds c itself. It takes attribute b of a first, which must be
                # the submodule a.b (checked by submodules() where a binds b itself)
                tgt = a.kids[0].s
                i = tgt.find(".")
                while tgt.find(".", i + 1) >= 0:
                    j = tgt.find(".", i + 1)
                    k = self.mods[tgt[:i]].kinds.get(tgt[i + 1 : j], "")
                    if k != "" and k != "m:" + tgt[:j]:
                        chk = mk("pass", "", line, [])
                        out.append(chk)
                        self.taken.append(mk("takemid", a.s, line, [mk("str", tgt[:i], line, []), mk("str", tgt[i + 1 : j], line, []), chk, mk("str", tgt, line, [])]))
                        self.takek.append(m.kinds)
                    i = j
                n = len(self.taken)
                if self.take(m, self.mods[tgt[: tgt.rfind(".")]], tgt[tgt.rfind(".") + 1 :], a.s, infn, keep, inits, copies, line) != "v":
                    flags[-1] = self.import_binds(m, a.s, infn)
                if len(self.taken) > n:
                    self.taken[n].kind = "takesub"  # (this import runs the submodule's code: submodules())
                names.append(a.s)
            elif st.s == "":
                # import a.b.c binds a; import a as x binds x to a
                self.bind(m, a.s, "m:" + a.kids[0].s, infn, line)
                names.append(a.s)
                flags[-1] = self.import_binds(m, a.s, infn)
            elif a.s == "*":
                for x in self.public(src):
                    mine = self.rebinds(m, src, x, x, infn)  # (a def or class statement of m binds x)
                    k = src.kinds[x] if mine else self.take(m, src, x, x, infn, keep, inits, copies, line)
                    took.append(" " if mine else x if k != "v" else "")
                    key = f"{src.name}  {x}"
                    checks.append(f"{self.fragile[key]} {x} I" if k != "v" and key in self.fragile else "")
                    if not mine:
                        names.append(x)
                if src.pdir != "" and not has_all(src.body.kids):
                    self.stars.append(mk("star", "", line, [mk("str", src.name, line, [])]))
                    self.starm.append(m)
            else:
                tgt = a.kids[0].s
                x = tgt[tgt.rfind(".") + 1 :]
                mine = self.rebinds(m, src, x, a.s, infn)
                k = src.kinds[x] if mine else self.take(m, src, x, a.s, infn, keep, inits, copies, line)
                took.append(" " if mine else a.s if k != "v" else "")
                key = f"{src.name}  {x}"
                checks.append(f"{self.fragile[key]} {x} I" if k != "v" and key in self.fragile else "")
                if not mine:
                    names.append(a.s)
        at.append(len(inits.kids))
        cat.append(len(copies))
        binds: list[Node] = []  # (a from-import's copies, and the bound nodes of its names that have flags, in order)
        c = 0
        for i in range(len(took)):
            nm = took[i]
            if nm == "":
                binds.append(copies[c])
                c += 1
                continue
            if nm == " ":
                if checks[i] != "":
                    b = mk("bound", "", line, [])  # (only the check: a def or class binds the name, rebinds())
                    b.mchk = checks[i]
                    binds.append(b)
                continue
            flags.append(self.import_binds(m, nm, infn))
            if flags[-1] != "" or checks[i] != "":
                b = mk("bound", flags[-1], line, [])
                b.mchk = checks[i]
                binds.append(b)
        inits.s = " ".join(names)  # (the names the statement binds, for deftime())
        for sub in inits.kids if self.intry > 0 else inits.kids[:0]:
            if "." in sub.s:
                self.trysubs[sub.s] = True
        if len(keep.kids) > 0:
            out.append(keep)
        if "".join(flags) == "" and "".join(checks) == "":
            if len(inits.kids) > 0:
                out.append(inits)
            out.extend(copies)
        elif st.s != "":
            if len(inits.kids) > 0:
                out.append(inits)
            out.extend(binds)
        else:
            for i in range(len(st.kids)):
                if at[i] < at[i + 1]:
                    out.append(mk("uimport", st.kids[i].s, line, inits.kids[at[i] : at[i + 1]]))
                out.extend(copies[cat[i] : cat[i + 1]])
                if flags[i] != "":
                    out.append(mk("bound", flags[i], line, []))

    def import_binds(self, m: Mod, name: str, infn: bool) -> str:
        # Module imports bind only where they run: an earlier read, a skipped branch or a call
        # during another module's initialization may find the name unbound. Every module binding
        # gets a flag. A function's imports need one where a try may skip or fail the import;
        # other early local reads are rejected by import_reads().
        if self.rtmode and not infn:
            return ""  # runtime mode accepts only unconditional module imports
        key = f"{m.name} {self.curdef if infn else ''} {name}"
        if not infn:
            self.fragile[key] = m.q + name
        elif self.intry == 0:
            self.solid[key] = True
        elif key not in self.solid:
            self.fragile[key] = name if infn else m.q + name
        return self.fragile.get(key, "")

    def chain(self, path: str, inits: Node) -> None:
        # the modules import path initializes: a, a.b, a.b.c
        i = 0
        while i >= 0:
            i = path.find(".", i + 1)
            p = path[:i] if i >= 0 else path
            inits.kids.append(mk("str", p, inits.line, []))

    def relative(self, m: Mod, s: str, path: str, line: int) -> str:
        # from .x import y in module m: the package m is in (m itself if it is one), one level
        # up per extra dot
        base = m.name if m.pdir != "" else m.name[: m.name.rfind(".")] if "." in m.name else ""
        if m.name == "" or (m.pdir == "" and "." not in m.name):
            fail("attempted relative import with no known parent package", line)
        for _ in range(len(s) - 5):
            if base == "":
                break
            base = base[: base.rfind(".")] if "." in base else ""
        if base == "":
            fail("attempted relative import beyond top-level package", line)
        return base + "." + path if path != "" else base

    def public(self, src: Mod) -> list[str]:
        # the names from src import * takes: those __all__ lists, else the names not starting with _
        out: list[str] = []
        found = False
        for st in src.body.kids:
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
                found = True
                out = []
                self.all_names(src, st.kids[1], out)
            elif st.kind == "augassign" and st.s == "+" and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
                self.all_names(src, st.kids[1], out)
            elif st.kind == "expr" and st.kids[0].kind == "call" and st.kids[0].kids[0].kind == "attr" and st.kids[0].kids[0].kids[0].kind == "name" and st.kids[0].kids[0].kids[0].s == "__all__":
                f = st.kids[0].kids[0].s
                args = st.kids[0].kids[1:]
                if f == "append" and len(args) == 1 and args[0].kind == "str":
                    out.append(args[0].s)
                elif f == "extend" and len(args) == 1:
                    self.all_names(src, args[0], out)
                else:
                    fail(f"from {src.name} import *: __all__.{f}() is not supported (only assigning, +=, append and extend)", st.line)
        if found:
            return out
        dels: dict[str, bool] = {}
        deleted(src.body.kids, dels)
        for nm in src.kinds:
            if not nm.startswith("_") and nm not in dels and nm not in src.fnonly:
                out.append(nm)
        return out

    def all_names(self, src: Mod, v: Node, out: list[str]) -> None:
        # the strings of a list or tuple literal assigned to or added to __all__ (or a + of those)
        if v.kind == "binop" and v.s == "+":
            self.all_names(src, v.kids[0], out)
            self.all_names(src, v.kids[1], out)
        elif v.kind == "list" or v.kind == "tuple":
            for x in v.kids:
                if x.kind != "str":
                    fail(f"from {src.name} import *: __all__ must list strings", x.line)
                out.append(x.s)
        else:
            fail(f"from {src.name} import *: __all__ must be a list or tuple of strings", v.line)

    def rebinds(self, m: Mod, src: Mod, x: str, name: str, infn: bool) -> bool:
        # from src import x as name (or *) in module code, of a function or class of src's (whose
        # code has run), where only a def or class statement after it binds name besides: CPython's
        # import binds src's x until that statement rebinds name. The statement's binding
        # (m.kinds) stands for all of m's code, and the import binds nothing (it checks that src has
        # bound x, as for a name it binds), where nothing may read the import's: neither code from
        # the import on that runs before the statement binds name (its decorators, defaults,
        # annotations, bases and class body too), nor a function or class defined before it that
        # uses name, or one that does, where code before it names one (which may run it, or keep
        # it) or decorates one, nor a lambda or generator expression before it that reads name
        # (else an error). Another module's code that reads it during an import cycle finds it
        # unbound (NameError, AttributeError: docs). False where the import binds name (take())
        k = m.kinds.get(name, "")
        sk = src.kinds.get(x, "")
        if infn or (k != "f" and k != "c") or src.name == m.name or not src.done or not (sk == "f" or sk == "c" or sk.startswith("a:")):
            return False
        body = m.body.kids
        s = 0
        while s < len(body) and body[s].line != m.at:
            s += 1
        d = s + 1
        while d < len(body) and not ((body[d].kind == "def" or body[d].kind == "class" or body[d].kind == "subclass") and body[d].s == name):
            d += 1
        if d >= len(body):
            return False
        others: dict[str, bool] = {}
        binds([st for st in body[:s] + body[s + 1 : d] + body[d + 1 :] if st.kind != "import"], others, True)  # (another import is checked so too)
        if name in others or declares(body, name):
            return False
        uses: dict[str, bool] = {name: True}  # (and the functions and classes before the statement that use it)
        grew = True
        while grew:
            grew = False
            for st in body[:d]:
                if (st.kind == "def" or st.kind == "class" or st.kind == "subclass") and st.s not in uses and first_use(st, uses, False) is not None:
                    uses[st.s] = True
                    grew = True
        fns = dict(uses)
        del fns[name]
        own: dict[str, bool] = {name: True}
        what = f"'{name}' is bound both by an import and by a def or class, and "
        for i in range(d + 1):
            st = body[i]
            r = deferred_use(st, own)  # (also one made before the import, which may be kept)
            if r is not None:
                fail(what + "a lambda or generator expression here that reads it may run in between (not supported)", r.line)
            r = first_use(st, uses, True) if i >= s else first_use(st, fns, True) if len(fns) > 0 else None
            if r is not None:
                nm = r.s.split(".")[0]
                fail(what + ("is read here in between" if nm == name else f"'{nm}', which uses it, may run in between") + " (not supported)", r.line)
            c = st.kids[0] if st.kind == "subclass" else st
            for dx in c.kids[3:] if st.kind == "def" else c.kids[1:] if st.kind == "class" or st.kind == "subclass" else st.kids[:0]:
                if dx.kind == "deco" and dx.s != "async" and (st.s in fns or (i == d and first_use(st, uses, False) is not None)):
                    fail(what + "a decorator here may run a function or class that uses it in between (not supported)", dx.line)
        return True

    def take(self, m: Mod, src: Mod, x: str, name: str, infn: bool, keep: Node, inits: Node, copies: list[Node], line: int) -> str:
        # from src import x as name; what x is in src ("" for a submodule, "v" for a variable, which
        # an assignment copies)
        if src.name in GLUE and m.name not in GLUE and x not in GLUE[src.name]:
            fail(f"cannot import name '{x}' from '{src.name}': Pystachy's {src.name} module offers {', '.join(GLUE[src.name])} (as its twin, tools/rt_cpython/{src.name}.py, does)", line)
        k = src.kinds.get(x, "")
        if src.name == m.name and not infn and x not in self.sure:
            # (from . import x in a package's own code takes the package's x if its code has bound x
            # by then, else the submodule)
            if x in self.maybe or "*" in self.maybe or x in m.fnglobal:
                fail(f"'{x}' is the package's own '{x}' if its code has bound it before this import, else the submodule '{m.name}.{x}', and Pystachy cannot tell which (not supported)", line)
            k = ""
        if not infn and (m.kinds.get(name, "") == "f" or m.kinds.get(name, "") == "c"):
            fail(f"'{name}' is bound both by an import and by a def or class (not supported)", line)
        if x == "__doc__" and k == "":
            # src's docstring or None (qexpr() reads it), copied as a variable is
            if not infn:
                if m.kinds.get(name, "v") != "v":
                    fail(f"'{name}' is bound both as a variable and by an import (not supported)", line)
                m.kinds[name] = "v"
            copies.append(mk("assign", "from", line, [mk("name", name, line, []), mk("moddoc", src.name, line, [])]))
            return "v"
        if not infn and m.kinds.get(name, "") == "v" and k != "v" and (k != "" or src.pdir != ""):
            fail(f"'{name}' is bound both as a variable and by an import (not supported)", line)
        if k == "" and src.pdir != "":
            # a submodule of the package
            sub = src.name + "." + x
            if self.modpath(sub) == "":
                fail(f"'{x}' from '{src.name}' is not supported: no definition or submodule was found on the module path", line)
            self.find(sub, line)
            inits.kids.append(mk("str", sub, line, []))
            self.bind(m, name, "m:" + sub, infn, line)
        elif k == "":
            fail(f"cannot import name '{x}' from '{src.name}'", line)
        elif k == "f" or k == "c":
            self.bind(m, name, "a:" + src.q + x, infn, line)
        elif k.startswith("b:"):
            p = k[2:]
            self.bind(m, name, k, infn, line)
            if infn or not (p.startswith("builtins.") and is_excname(p[9:])):  # (qname() names a builtin exception class itself)
                keep.kids.append(mk("alias", name, line, [mk("str", p, line, []), mk("str", builtin_of(p), line, [])]))
        elif k != "v":
            al = self.aliased.get(src.name + " " + x, None)
            if k.startswith("t:") and al is not None and not src.done and src.at > 0 and al.line > src.at:
                # (a type statement, taken while src's code ran an import above it: CPython raises
                # ImportError; late_takes checks the other type aliases and TypeVars)
                fail(f"cannot import name '{x}' from '{src.name}' here: its code binds it only after the import that runs this one (not supported for a type alias)", line)
            self.bind(m, name, k, infn, line)
        else:
            ks = self.fks[self.curdef] if infn else m.kinds
            at = self.curdef if infn else "@" + m.name
            was = ks.get(name, "")
            if was == "v" and at + " " + name in self.vtook:
                was = ""  # (another from-import of a variable bound it: see late_takes())
            elif was != "v":
                self.vtook[at + " " + name] = True
            if not infn:
                m.kinds[name] = "v"
            copies.append(mk("assign", "from", line, [mk("name", name, line, []), mk("name", src.q + x, line, [])]))
            self.vtaken.append(mk("vtake", name, line, [mk("str", src.name, line, []), mk("str", x, line, []), copies[-1], mk("str", was, line, []), mk("str", at, line, []),
                                                       mk("int", str(src.at if not src.done else 0), line, [])]))
            self.vtakek.append(ks)
        if src.pdir != "" and k != "" and k != "m:" + src.name + "." + x:
            # the package binds x itself, which an import of its submodule x may rebind (submodules())
            self.taken.append(mk("take", name, line, [mk("str", src.name, line, []), mk("str", x, line, [])] + (copies[-1:] if k == "v" else copies[:0])))
            self.takek.append(self.fks[self.curdef] if infn else m.kinds)
        return k

    # ---- qualification of names
    def kind(self, m: Mod, s: str) -> str:
        # what s is bound to in m, where an import in the function being qualified comes first
        return self.fk[s] if s in self.fk else m.kinds.get(s, "")

    def qname(self, m: Mod, s: str, loc: dict[str, bool]) -> str:
        if s in loc or "$" in s:
            return s
        if s in self.qren:
            return self.qren[s]
        k = self.kind(m, s)
        if k.startswith("b:builtins.") and is_excname(k[11:]) and s not in self.fk:
            return k[11:]  # (a builtin exception class by another name: from builtins import RuntimeError as error)
        if k == "f" or k == "c" or k == "v" or k.startswith("b:"):
            if m.name == "" and s in PYBUILTINS:
                return "__main__$" + s  # (other modules' code still sees the builtin)
            return m.q + s
        if k.startswith("a:") or k.startswith("t:"):
            return k[2:]
        if k == "" and m.name != "" and s not in PYBUILTINS and not s.startswith("__"):
            return m.q + s  # not defined (the main program's names are not a module's)
        return s

    def qmod(self, m: Mod, n: Node, loc: dict[str, bool]) -> str:
        # the module n denotes (a name bound to one, or a submodule attribute of one), or "";
        # an attribute of a module that is not a module is rewritten to its qualified name
        if n.kind == "name":
            k = self.kind(m, n.s) if n.s not in loc else ""
            return k[2:] if k.startswith("m:") else ""
        if n.kind != "attr":
            return ""
        base = self.qmod(m, n.kids[0], loc)
        if base == "":
            return ""
        if n.s == "__name__":
            n.kind = "str"
            n.s = base
            n.kids = []
            return ""
        t = self.mods[base]
        if n.s == "__doc__" and "__doc__" not in t.kinds:
            self.moddoc(n, t)
            return ""
        k = t.kinds.get(n.s, "")
        key = f"{base}  {n.s}"
        if key in self.fragile:
            # The importing name and the source module's attribute are distinct bindings.
            self.subchk.append(f"{self.fragile[key]} {n.s} M")
        if n.s in t.amb:
            k = "x:" + self.ambiguous(base, n.s)
        if base in GLUE and m.name not in GLUE and n.s not in GLUE[base]:
            k = f"x:{base}.{n.s} is not offered by Pystachy's {base} module, whose names are {', '.join(GLUE[base])}"
        if k.startswith("m:"):
            return k[2:]
        if k == "" and base + "." + n.s in self.mods:
            if base + "." + n.s in self.trysubs:
                self.subchk.append(f"{base}.{n.s} {n.s} A")
            return base + "." + n.s  # a submodule (unless the package binds the name itself)
        if k == "":
            n.kind = "badattr"
            n.s = f"module attribute '{n.s}' is not supported" if n.s in (MODDUNDERS + " __dict__ __cached__").split() or (n.s == "__path__" and t.pdir != "") else f"module '{base}' has no attribute '{n.s}'"
        elif k.startswith("x:"):
            n.kind = "badattr"
            n.s = k[2:]
        else:
            n.kind = "name"
            n.s = self.qname(t, n.s, {})
        n.kids = []
        return ""

    def qexpr(self, m: Mod, n: Node, loc: dict[str, bool]) -> None:
        k = n.kind
        if k == "name" or k == "attr":
            if k == "name" and n.s == "__name__" and (m.name != "" or self.ext != "") and n.s not in loc:
                if "__name__" in m.rebound:
                    fail(f"module '{m.name if m.name != '' else self.ext}' binds __name__, which is not supported in an imported module", n.line)
                n.kind = "str"
                n.s = m.name if m.name != "" else self.ext
                return
            if k == "name" and n.s == "__debug__":
                n.kind = "True"  # (CPython runs without -O; nothing can bind __debug__)
                return
            if k == "name" and n.s == "__doc__" and n.s not in loc and n.s not in self.fk and n.s not in m.kinds:
                self.moddoc(n, m)
                return
            root = n
            while root.kind == "attr":
                root = root.kids[0]
            if root.kind == "name" and root.s not in loc and root.s in self.fkowner and self.fkowner[root.s] != self.fkey:
                # A named closure can resolve an enclosing import, but cannot yet take its
                # possibly-unbound binding flag as a lambda does. Reject instead of reading
                # the imported value even when that import raised or was skipped.
                key = f"{m.name} {self.fkowner[root.s]} {root.s}"
                if key in self.fragile:
                    n.kind = "badattr"
                    n.s = f"a def inside a function reads enclosing import '{root.s}', which may be unbound (not supported)"
                    n.kids = []
                    return
            chks: list[str] = []
            if root.kind == "name" and self.fragile_chk(m, root.s, loc) != "":
                chks.append(self.fragile_chk(m, root.s, loc))
            self.subchk = []
            mod = self.qmod(m, n, loc)
            chks.extend(self.subchk)
            r = n
            while r.kind == "attr":
                r = r.kids[0]  # (m.C.k: the name qmod() made of m.C is what is read)
            if len(chks) > 0 and (r.kind == "name" or r.kind == "str"):
                r.mchk = ";".join(chks)
            if mod != "":
                n.kind = "badattr"
                n.s = f"module '{mod}' cannot be used as a value"
                n.kids = []
            elif n.kind == "name" and n.s not in loc and self.kind(m, n.s).startswith("x:"):
                n.kind = "badattr"
                n.s = self.kind(m, n.s)[2:]
            elif n.kind == "name" and n.s not in loc and n.s not in self.fk and n.s in m.amb and (self.qdef or m.amb[n.s]):
                # a package's own name that an import of its submodule may have rebound (submodules())
                n.kind = "badattr"
                n.s = self.ambiguous(m.name, n.s)
            elif n.kind == "name":
                n.s = self.qname(m, n.s, loc)
            elif n.kind == "attr":
                self.qexpr(m, n.kids[0], loc)
        elif k == "moddoc":
            self.moddoc(n, self.mods[n.s])  # (from m import __doc__: take())
        elif k == "lambda":
            # lambda params: body: its defaults are evaluated where it is, its body sees its parameters
            # and the names of the function around it
            for p in n.kids[0].kids:
                self.qexpr(m, p.kids[1], loc)
            inner = dict(loc)
            if not inner.get("__doc__", True):
                del inner["__doc__"]  # (a class body's: qstmts())
            for p in n.kids[0].kids:
                inner[p.s] = True
            walrus_names(n.kids[1], inner)  # (and the names its := bind)
            self.qexpr(m, n.kids[1], inner)
        elif k == "walrus":
            # x := v binds x where an assignment to x would (in a comprehension, around it)
            self.qexpr(m, n.kids[0], loc)
            n.s = self.qname(m, n.s, loc)
        elif k == "listcomp":
            # [element for target in iterable if condition]: the targets' names are the comprehension's
            # (added to loc while the rest is qualified, not to a copy: loc has all of a function's locals)
            self.qexpr(m, n.kids[2], loc)
            names: list[str] = []
            comp_names(n, names)
            doc = not loc.get("__doc__", True)  # (a class body's: qstmts())
            if doc:
                del loc["__doc__"]
            added: list[str] = []
            for nm in names:
                if nm not in loc:
                    loc[nm] = True
                    added.append(nm)
            for i in range(len(n.kids)):
                if i != 2:
                    self.qexpr(m, n.kids[i], loc)
            for nm in added:
                del loc[nm]
            if doc:
                loc["__doc__"] = False
        else:
            # (a comprehension's iterable is qualified where it is, its other parts in its own scope,
            # where __doc__ is not a class body's: qstmts())
            doc = (k == "nestedcomp" or k == "asynccomp") and not loc.get("__doc__", True)
            for i in range(len(n.kids)):
                if doc and i != 2:
                    del loc["__doc__"]
                self.qexpr(m, n.kids[i], loc)
                if doc and i != 2:
                    loc["__doc__"] = False

    def qstore(self, m: Mod, t: Node, loc: dict[str, bool]) -> None:
        # an assignment target: a package's own name that an import of its submodule may rebind
        # (Mod.amb) cannot be assigned from another module, as which of the two it replaces is not known
        if t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
            for x in t.kids:
                self.qstore(m, x, loc)
            return
        b = self.modof(m, t.kids[0], loc) if t.kind == "attr" else ""
        if b != "" and t.s == "__doc__" and "__doc__" not in self.mods[b].kinds:
            t.kind = "badattr"
            t.s = f"assigning the __doc__ of module '{b}' is not supported"
            t.kids = []
            return
        if b != "" and t.s in self.mods[b].amb:
            t.kind = "badattr"
            t.s = f"assigning '{b}.{t.s}' is not supported: the program's first import of the submodule '{b}.{t.s}' binds it too"
            t.kids = []
        self.qexpr(m, t, loc)

    def modof(self, m: Mod, n: Node, loc: dict[str, bool]) -> str:
        # the module n denotes, as qmod() finds it but without rewriting n, or ""
        if n.kind == "name":
            k = self.kind(m, n.s) if n.s not in loc else ""
            return k[2:] if k.startswith("m:") else ""
        base = self.modof(m, n.kids[0], loc) if n.kind == "attr" else ""
        if base == "" or n.s in self.mods[base].amb:
            return ""
        k = self.mods[base].kinds.get(n.s, "")
        if k.startswith("m:"):
            return k[2:]
        return base + "." + n.s if k == "" and base + "." + n.s in self.mods else ""

    def qann(self, m: Mod, n: Node, loc: dict[str, bool]) -> None:
        # an annotation; a string one (a forward reference), also inside list["Node"], is parsed
        # to qualify the names in it
        if n.kind == "str":
            e = Parser(Lexer(n.s, n.line).run()).test()
            n.kind = e.kind
            n.s = e.s
            n.kids = e.kids
        if n.kind == "index" or n.kind == "tuple" or (n.kind == "binop" and n.s == "|"):
            for k in n.kids:
                self.qann(m, k, loc)
        else:
            self.qexpr(m, n, loc)
            if n.chk and n.kind == "badattr" and " has no attribute " in n.s:
                fail(n.s, n.line)  # (an evaluated annotation: see Loader.reads)

    def fragile_chk(self, m: Mod, x: str, loc: dict[str, bool]) -> str:
        # the check (Node.mchk) of a read of name x in m, where an import in a try statement binds
        # it: its flag, x and whether it is a function's (L) or module code's (G); "" elsewhere
        if x in loc:
            return ""
        inf = x in self.fk
        key = f"{m.name} {self.fkey if inf else ''} {x}"
        return f"{self.fragile[key]} {x} {'L' if inf else 'G'}" if key in self.fragile else ""

    def qdeco(self, m: Mod, d: Node, loc: dict[str, bool], fn: bool = False) -> None:
        # a decorator: the first name of its dotted name (unless it surely names a builtin
        # there: deftime), and the arguments of a call. A def's (fn), which CPython calls on the
        # function (Gen.decorate), names what it is: an imported function or class (not as written),
        # and an attribute of a module as its qualified name; a call's function is qualified too.
        # A dotted name's first name that an import in a try statement binds is checked as a read
        # of it is (Node.mchk, which Gen.decorate tests where CPython evaluates the decorator)
        root = d.s[: d.s.find(".")] if "." in d.s else d.s
        k = self.kind(m, root) if root not in loc else ""
        q = k[2:] if k.startswith("a:") and root == d.s else "abc$" + d.s[len(root) + 1 :] if k == "m:abc" and "." in d.s else ""
        if not fn and len(d.kids) == 0 and q in ABSTRACT_DECOS:
            # (a method's @abstractmethod, or one of the decorators deprecated for it, as abc's:
            # the compiler applies it, Gen.abstract_defs)
            d.s = q
            return
        alias = root not in loc and self.kind(m, root).startswith("a:") and not fn  # (shown as written: m$root)
        if fn and "." in d.s and root not in loc and self.kind(m, root).startswith("m:"):
            e = mk("name", root, d.line, [])
            for part in d.s.split(".")[1:]:
                e = mk("attr", part, d.line, [e])
            self.qexpr(m, e, loc)
            d.s = e.s if e.kind == "name" else d.s
            r = e
            while r.kind == "attr":
                r = r.kids[0]
            d.mchk = r.mchk if len(d.kids) == 0 else ""
        else:
            if fn and len(d.kids) == 0 and d.line not in self.bdecos:
                d.mchk = self.fragile_chk(m, root, loc)
            d.s = (root if d.line in self.bdecos else m.q + root if alias else self.qname(m, root, loc)) + d.s[len(root) :]
        for c in d.kids:
            if fn:
                self.qexpr(m, c.kids[0], loc)
            for a in c.kids[1:]:
                self.qexpr(m, a, loc)

    def qstmts(self, m: Mod, body: list[Node], loc: dict[str, bool], cls: bool) -> None:
        for st in body:
            k = st.kind
            if k == "def":
                if not cls:
                    st.s = self.qname(m, st.s, loc)
                for d in st.kids[3:]:
                    if d.s != "async":
                        self.qdeco(m, d, loc, not cls)
                for p in st.kids[0].kids:
                    self.qann(m, p.kids[0], loc)
                    self.qexpr(m, p.kids[1], loc)
                self.qann(m, st.kids[1], loc)
                # (a def in a function sees that function's names too: those it does not bind itself
                # are the enclosing function's, which a closure reads)
                own: dict[str, bool] = {}
                for p in st.kids[0].kids:
                    own[p.s] = True
                local_names(st.kids[2].kids, own)
                inner: dict[str, bool] = dict(loc) if self.qdef and not cls else {}
                for nm in own:
                    inner[nm] = True
                decl: dict[str, bool] = {}
                globals_in(st.kids[2].kids, decl)
                for nm in decl:
                    if nm in inner:
                        del inner[nm]
                    if nm in own:
                        del own[nm]
                saved = self.fk
                owners = self.fkowner
                key = self.fkey
                indef = self.qdef
                imports = self.fks.get(str(st.line), {})
                self.fk = {}
                self.fkowner = {}
                # The closest function's import wins. Its parameters, variables and global
                # declarations hide enclosing imports just as they hide enclosing variables.
                for nm in saved:
                    if indef and not cls and nm not in own and nm not in decl:
                        self.fk[nm] = saved[nm]
                        self.fkowner[nm] = owners[nm]
                for nm in imports:
                    self.fk[nm] = imports[nm]
                    self.fkowner[nm] = str(st.line)
                    if nm in inner and nm not in own:
                        del inner[nm]  # (this import hides an enclosing function's variable)
                for nm in self.unsure.get(str(st.line), {}):
                    k = imports.get(nm, "")
                    if k.startswith("m:") or k.startswith("a:") or k.startswith("b:"):
                        # (a function's import of a Python module binds a local, which CPython reads
                        # unbound before it runs)
                        st.kids[2].kids.insert(0, mk("badimport", f"'{nm}' is read in {st.s}() where Pystachy cannot tell that the import in it that binds '{nm}' has run (where it has not, CPython raises UnboundLocalError): not supported", st.line, []))
                        break
                for nm in imports:
                    if nm in own:
                        # (one binding per name, as in module code: CPython's import rebinds the
                        # function's variable, which every read of the name here would read)
                        at = self.fkline.get(f"{st.line} {nm}", st.line)
                        st.kids[2].kids.insert(0, mk("badimport", f"'{nm}' is bound both as a variable and by an import (not supported)", at, []))
                        break
                self.fkey = str(st.line)
                self.qdef = True
                ren = self.qren
                self.qren = dict(ren)
                for nm in st.kids[2].s.split():
                    # (a generic def's type parameters, in its body as a generic class's are in its
                    # methods: CPython's TypeVars, not the module's or an enclosing function's
                    # names, which they hide)
                    self.qren[nm] = st.s + "$$" + nm
                    m.deftps.append(self.qren[nm])
                    if nm not in own:
                        inner.pop(nm, False)
                for nm in decl:
                    self.qren.pop(nm, "")  # (global T in a method of class C[T]: the module's T)
                self.qstmts(m, st.kids[2].kids, inner, False)
                self.qren = ren
                self.qdef = indef
                self.fk = saved
                self.fkowner = owners
                if cls:
                    loc[st.s] = True
                self.fkey = key
            elif k == "subclass":
                # (a generic class's type parameters: in its bases, body and methods, names of
                # their own, qren's)
                outer = self.qren
                self.qren = dict(outer)
                params = st.kids[1].s.split() if st.kids[1].kind == "typeparams" else []
                for nm in params:
                    self.qren[nm] = self.qname(m, st.s, loc) + "$$" + nm
                st.kids[1].s = " ".join([self.qren[nm] for nm in params]) if len(params) > 0 else st.kids[1].s
                self.qstmts(m, [st.kids[0]], loc, cls)
                st.s = st.kids[0].s
                for kid in st.kids[1:]:
                    self.qexpr(m, kid, loc)
                self.qren = outer
                if cls:
                    loc[short(st.s)] = True
            elif k == "class":
                # (a class body's own names, in loc once bound, stay unqualified where it reads them)
                st.s = self.qname(m, st.s, loc)
                for d in st.kids[1:]:
                    self.qdeco(m, d, loc)
                # (class scopes do not nest; a class body's __doc__ is the class's docstring, which
                # cannot be read: it stays unqualified, an error in Gen. False: not in the lambdas
                # and comprehensions of the body, which read the module's)
                cloc: dict[str, bool] = {} if cls else dict(loc)
                if "__doc__" not in cloc:
                    cloc["__doc__"] = False
                self.qstmts(m, st.kids[0].kids, cloc, True)
                if cls:
                    loc[short(st.s)] = True
            elif cls and k == "assign":
                # a class attribute: the names it binds are the class's
                self.qexpr(m, st.kids[-1], loc)
                for kid in st.kids[:-1]:
                    if kid.kind != "name" and kid.kind != "tuple":
                        self.qexpr(m, kid, loc)
                collect([st], loc)
            elif cls and k == "annassign" and st.kids[0].kind == "name":
                # a field: the name is the class's, the annotation and default value the module's
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
                if len(st.kids) == 3:
                    loc[st.kids[0].s] = True
            elif k == "annassign" and not self.qdef and not cls and len(st.kids) == 3 and st.kids[0].kind == "name" and (self.is_alias(m, st) or self.kind(m, st.kids[0].s).startswith("a:")):
                # name: TypeAlias = value (late_aliases), once deftime has checked it: name = value,
                # but name = C of a class is no statement (as bindings makes it), and a string, a
                # forward reference, is as lazy as a type statement's value
                v = st.kids[2]
                if self.kind(m, st.kids[0].s).startswith("a:"):
                    st.kind = "pass"
                    st.kids = [st.kids[0], v]
                elif v.kind == "str":
                    st.kind = "typealias"
                    st.s = st.kids[0].s
                    st.kids = [mk("typeparams", "", st.line, [v])]
                    self.qstmts(m, [st], loc, cls)
                else:
                    st.kind = "assign"
                    st.s = ""
                    st.kids = [st.kids[0], v]
                    self.qstmts(m, [st], loc, cls)
            elif k == "annassign":
                self.qstore(m, st.kids[0], loc)
                self.qann(m, st.kids[1], loc)
                for kid in st.kids[2:]:
                    self.qexpr(m, kid, loc)
            elif k == "assign":
                alias = not self.qdef and not cls and self.is_alias(m, st)
                for kid in st.kids[:-1]:
                    self.qstore(m, kid, loc)
                if alias:
                    self.qann(m, st.kids[-1], loc)  # (a type alias's value, where strings are forward references)
                else:
                    self.qexpr(m, st.kids[-1], loc)
            elif k == "typealias" and len(st.kids) > 0:
                # type X[T] = value: the value is an annotation that sees the type parameters
                tps = dict(loc)
                for nm in st.kids[0].s.split():
                    tps[nm] = True
                self.qann(m, st.kids[0].kids[0], tps)
                st.s = self.qname(m, st.s, loc)
            elif k == "import" or k == "global":
                for a in st.kids:
                    a.s = self.qname(m, a.s, {})
            elif k != "uimport":
                for kid in st.kids:
                    if kid.kind == "block":
                        self.qstmts(m, kid.kids, loc, cls)
                    elif kid.kind == "except":
                        # except E as e: E is read, and e bound, like any other name
                        self.qexpr(m, kid.kids[0], loc)
                        if kid.s != "":
                            kid.s = self.qname(m, kid.s, loc)
                        self.qstmts(m, kid.kids[1].kids, loc, cls)
                    else:
                        self.qexpr(m, kid, loc)


# ---------------------------------------------------------------- types
# A type is a canonical string: int float bool str None file, list[T], dict[K,V],
# tuple[A,B], or a class name. LLVM view: i64, double, i1, void, everything else ptr.
