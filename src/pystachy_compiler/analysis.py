"""Analysis component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.specs import ABCS, ABCSMORE, CALLS, CTYPES, ERRNO, FUTURE, MODATTRS, MODFUNCS, MODULES, NOREF, RANGE_METHODS, RANGE_TAKERS, TYPING
from src.pystachy_compiler.syntax import Node, comp_names, has_kind, mentions, mk, names_in, other_return, starred_target
from src.pystachy_compiler.utils import int_fits


def target_names(t: Node, out: dict[str, bool]) -> None:
    # the names target t binds, into a dict (names_in)
    ns: list[str] = []
    names_in(t, ns)
    for nm in ns:
        out[nm] = True


def walrus_names(e: Node, out: dict[str, bool]) -> None:
    # x := v binds x in the enclosing function, also inside a comprehension or a lambda's
    # defaults (not in its body)
    if e.kind == "walrus":
        out[e.s] = True
    if e.kind == "lambda":
        for p in e.kids[0].kids:
            walrus_names(p.kids[1], out)
    else:
        for k in e.kids:
            walrus_names(k, out)


def walrus_values(e: Node, name: str, out: list[Node]) -> None:
    # the values that the := of name in expression e assign, in the order they run (as
    # walrus_names finds them)
    for k in e.kids if e.kind != "lambda" else [p.kids[1] for p in e.kids[0].kids]:
        walrus_values(k, name, out)
    if e.kind == "walrus" and e.s == name:
        out.append(e.kids[0])


def none_sites(body: list[Node], out: dict[str, list[Node]]) -> None:
    # the statements in body (into blocks, in order, not into the functions and classes it
    # defines) whose own code may assign each name, as Gen.none_values reads them: a name or a
    # tuple or list target's name item, and a := in a kid that is no block
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        names: dict[str, bool] = {}
        for t in st.kids[:-1] if st.kind == "assign" else st.kids[:0]:
            for x in t.kids if t.kind == "tuple" or t.kind == "list" else [t]:
                if x.kind == "name":
                    names[x.s] = True
        for kid in st.kids:
            if kid.kind != "block" and kid.kind != "except":
                walrus_names(kid, names)
        for nm in names:
            if nm not in out:
                out[nm] = []
            out[nm].append(st)
        for kid in st.kids:
            if kid.kind == "block":
                none_sites(kid.kids, out)
            elif kid.kind == "except":
                none_sites(kid.kids[1].kids, out)


def stmt_walrus(st: Node, out: dict[str, bool]) -> None:
    # the names that the := in statement st's own expressions bind (not in its blocks, nor in the
    # body of the class or function it defines)
    if st.kind == "subclass":
        for x in st.kids[0].kids[1:] + st.kids[1:]:
            walrus_names(x, out)
        return
    for kid in st.kids:
        if kid.kind == "except":
            walrus_names(kid.kids[0], out)
        elif st.kind == "async":
            stmt_walrus(kid, out)
        elif kid.kind != "block":
            walrus_names(kid, out)


def scope_binds(body: list[Node], out: dict[str, bool], decl: dict[str, str]) -> None:
    # the names a function's body binds (not those of the functions and classes in it), and in
    # decl those its global and nonlocal statements declare
    for st in body:
        k = st.kind
        if k == "global" or k == "nonlocal":
            for g in st.kids:
                decl[g.s] = k
        elif k == "def":
            # (with its defaults, annotations and decorators, which run here)
            out[st.s] = True
            for p in st.kids[0].kids:
                walrus_names(p.kids[0], out)
                walrus_names(p.kids[1], out)
            for x in [st.kids[1]] + st.kids[3:]:
                walrus_names(x, out)
        elif k == "class" or k == "subclass":
            # (with its decorators and bases)
            c = st if k == "class" else st.kids[0]
            out[c.s] = True
            for x in c.kids[1:] + (st.kids[1:] if k == "subclass" else []):
                walrus_names(x, out)
        elif k == "typealias":
            out[st.s] = True
        elif k == "import":
            for a in st.kids:
                if a.s != "*":
                    out[a.s] = True
        elif k == "assign" or k == "del":
            for t in st.kids if k == "del" else st.kids[:-1]:
                target_names(t, out)
        elif (k == "annassign" and (st.s == "" or len(st.kids) == 3)) or k == "augassign" or k == "for":
            target_names(st.kids[0], out)
        elif k == "with":
            for it in st.kids[:-1]:
                if len(it.kids) == 2:
                    target_names(it.kids[1], out)
        if k != "def" and k != "class" and k != "subclass":
            for kid in st.kids:
                if kid.kind == "block":
                    scope_binds(kid.kids, out, decl)
                elif kid.kind == "except":
                    if kid.s != "":
                        out[kid.s] = True
                    walrus_names(kid.kids[0], out)
                    scope_binds(kid.kids[1].kids, out, decl)
                elif k == "async":
                    scope_binds([kid], out, decl)
                else:
                    for nm in kid.s.split() if kid.kind == "pattern" else []:
                        out[nm] = True  # (a match statement's captures)
                    walrus_names(kid, out)


def builtin_module(path: str) -> bool:
    root = path[: path.find(".")] if "." in path else path
    return path in MODULES or root in MODULES or path == "collections.abc"


def clean_doc(s: str) -> str:
    # a docstring as CPython 3.13's compiler keeps it (_PyCompile_CleanDoc): tabs expanded (in
    # columns of characters, which UTF-8 continuation bytes do not start), the first line's leading
    # spaces and the indentation that the other lines with text share removed
    out: list[str] = []
    col = 0
    for i in range(len(s)):
        c = s[i]
        if c == "\t":
            out.append(" " * (8 - col % 8))
            col += 8 - col % 8
        else:
            out.append(c)
            col = 0 if c == "\n" or c == "\r" else col if ord(c) & 192 == 128 else col + 1
    lines = "".join(out).split("\n")
    margin = -1
    for ln in lines[1:]:
        k = len(ln) - len(ln.lstrip(" "))
        if k < len(ln) and (margin < 0 or k < margin):
            margin = k
    kept = [lines[0].lstrip(" ")]
    for ln in lines[1:]:
        kept.append(ln[min(margin, len(ln) - len(ln.lstrip(" "))) if margin > 0 else 0 :])
    return "\n".join(kept)


def names_name(n: Node, name: str) -> bool:
    # does code n name name anywhere: reads, binds or declares it, also in the functions and
    # classes it defines (an import's alias of that name too)
    if (n.kind == "name" or n.kind == "alias") and n.s == name:
        return True
    for k in n.kids:
        if names_name(k, name):
            return True
    return False


def binds_first(st: Node, name: str) -> bool:
    # does module-level statement st bind name for sure without reading it first: name = v (also
    # among other names), name: T = v, or an import of that name
    if st.kind == "import":
        return True  # (its alias: names_name())
    if st.kind != "assign" and not (st.kind == "annassign" and len(st.kids) == 3):
        return False
    for t in st.kids[:-1] if st.kind == "assign" else st.kids[:1]:
        if t.kind != "name":
            return False
    return not names_name(st.kids[-1], name)


def del_line(n: Node, name: str, fn: bool) -> int:
    # the line of a del statement in code n that deletes the module's name: outside functions and
    # classes (not fn), or in a function that declares it global; 0 if there is none
    if n.kind == "def":
        decl: dict[str, bool] = {}
        globals_in(n.kids[2].kids, decl)
        fn = name not in decl
    elif n.kind == "class" or n.kind == "subclass":
        fn = True
    elif n.kind == "del" and not fn:
        for t in n.kids:
            names: list[str] = []
            if t.kind == "name" or t.kind == "tuple" or t.kind == "list":
                names_in(t, names)
            if name in names:
                return n.line
    for k in n.kids:
        r = del_line(k, name, fn)
        if r > 0:
            return r
    return 0


def builtin_import(st: Node, a: Node) -> bool:
    # does alias a of import statement st bind a builtin module or a name of one: import os.path
    # binds os, a builtin module, but import collections.abc the Python package collections
    return not st.s.startswith("from.") and builtin_module(a.kids[0].s if st.s == "" else a.kids[1].s)


def builtin_of(path: str) -> str:
    # the builtin module that path, a builtin module or a name of one, is in
    if path == "collections.abc" or path.startswith("collections.abc."):
        return "collections.abc"
    return path[: path.find(".")] if "." in path else path


def known_path(p: str) -> bool:
    # a module attribute Pystachy implements: a CALLS entry, a modattr() value, a module, a
    # function builtin() handles itself (MODFUNCS), sys.float_info (whose attributes are
    # modattr() values), or sys.version_info
    if p in MODULES or p in MODATTRS or p in MODFUNCS or p == "sys.float_info" or p == "sys.implementation" or p == "sys.version_info" or p == "os.PathLike" or (p.startswith("errno.") and p[6:] in ERRNO):
        return True
    for k in CALLS:
        if k.startswith(p + "(") or k.startswith(p + "."):
            return True
    return False


def builtin_has(mod: str, x: str) -> bool:
    # may from mod import x name x, of Pystachy's builtin module mod
    if mod == "__future__":
        return x in FUTURE
    if mod == "typing":
        return x in TYPING
    if mod == "collections.abc":
        return x in ABCS or x in ABCSMORE  # (CPython's other names: rejected where imported)
    if mod == "dataclasses":
        return x == "dataclass"
    if mod == "ffi":
        return x in ("extern", "export", "string_at", "c_buf", "c_float") or x in CTYPES
    return mod == "builtins" or known_path(mod + "." + x)  # (a builtin is checked where it is called)


def accel_try(st: Node) -> bool:
    # try: <import statements, then others> / except ImportError: (or ModuleNotFoundError),
    # without finally
    if st.kind != "try" or len(st.kids) < 2 or st.kids[1].kind != "except" or len(st.kids[0].kids) == 0 or st.kids[0].kids[0].kind != "import":
        return False
    seen = False
    for x in st.kids[0].kids:
        if x.kind != "import":
            seen = True
        elif seen:
            return False
    for h in st.kids[1:]:
        if h.kind == "block" and h.s == "finally":
            return False
        if h.kind == "except":
            ts = h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]]
            for t in ts:
                if t.kind != "name" or (t.s != "ImportError" and t.s != "ModuleNotFoundError"):
                    return False
    return True


def catches_import(st: Node) -> bool:
    # may an except clause of try statement st catch ImportError (a bare except, or one naming it,
    # ModuleNotFoundError, Exception or BaseException)
    for h in st.kids[1:]:
        if h.kind == "except" and h.kids[0].kind == "omit":
            return True
        for t in (h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]]) if h.kind == "except" else h.kids[:0]:
            if t.kind == "name" and (t.s == "ImportError" or t.s == "ModuleNotFoundError" or t.s == "Exception" or t.s == "BaseException"):
                return True
    return False


def is_main_guard(e: Node) -> bool:
    # __name__ == "__main__"
    if e.kind != "cmp" or e.s != "==":
        return False
    a = e.kids[0]
    b = e.kids[1]
    if a.kind == "str":
        c = a
        a = b
        b = c
    return a.kind == "name" and a.s == "__name__" and b.kind == "str" and b.s == "__main__"


def has_all(body: list[Node]) -> bool:
    # does a module's top-level code assign __all__ (which from m import * then takes)
    for st in body:
        if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == "__all__":
            return True
    return False


def import_error(e: Node) -> str:
    # "ImportError" or "ModuleNotFoundError" if raise e raises it, else ""
    n = e.kids[0] if e.kind == "call" else e
    return n.s if n.kind == "name" and (n.s == "ImportError" or n.s == "ModuleNotFoundError") else ""


def may_end(n: Node, bare: bool) -> bool:
    # does n hold, outside the functions and classes it defines, a raise that re-raises (bare), or
    # else anything that may end the program: a raise, or a call of exit(), quit(), sys.exit(),
    # os._exit() or os.abort()
    if n.kind == "raise" and (len(n.kids) == 0 or not bare):
        return True
    for x in n.kids[:1] if n.kind == "call" and not bare else n.kids[:0]:
        if (x.kind == "name" and (x.s == "exit" or x.s == "quit")) or (x.kind == "attr" and (x.s == "exit" or x.s == "_exit" or x.s == "abort")):
            return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass":
        return False
    for k in n.kids:
        if may_end(k, bare):
            return True
    return False


def special_import(st: Node, a: Node) -> bool:
    # an import the loader recognizes where the name it binds is read: of a builtin module (import
    # os, import os.path as p), or from typing import TYPE_CHECKING
    if st.s == "":
        return builtin_import(st, a)
    return st.s == "from" and (a.kids[0].s == "typing.TYPE_CHECKING" or a.kids[0].s == "typing_extensions.TYPE_CHECKING")


def binds(body: list[Node], out: dict[str, bool], special: bool, pkg: str = "", deep: bool = True) -> None:
    # the names statements bind in their own scope (not inside the functions and classes they
    # define): assignments, del, def and class, except ... as, and imports (only with special those
    # special_import() recognizes; "*" for a star import; but in package pkg's code its own
    # from . import x of its submodule x, which binds x to that unless x is bound already); not in
    # their blocks unless deep
    for st in body:
        targets(st, out)
        if st.kind == "import":
            for a in st.kids:
                own = pkg != "" and a.s == a.kids[0].s[a.kids[0].s.rfind(".") + 1 :] and ((st.s == "from." and a.kids[1].s == "") or (st.s == "from" and a.kids[1].s == pkg))
                if (special or a.s == "*" or not special_import(st, a)) and not own:
                    out[a.s] = True
        elif st.kind == "del":
            for t in st.kids:
                if t.kind == "name":
                    out[t.s] = True
        elif st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            out[st.s] = True
            continue
        for kid in st.kids:
            if kid.kind == "block" and deep:
                binds(kid.kids, out, special, pkg)
            elif kid.kind == "except" and (special or not builtin_try(st)):
                if kid.s != "":
                    out[kid.s] = True
                binds(kid.kids[1].kids, out, special, pkg)


def builtin_try(st: Node) -> bool:
    # an optional import of builtin modules only (try: from typing import TYPE_CHECKING / except
    # ImportError: TYPE_CHECKING = False), whose except clauses never run (Loader.optional())
    for x in st.kids[0].kids if accel_try(st) else st.kids[:0]:
        for a in x.kids if x.kind == "import" else x.kids[:0]:
            if x.s.startswith("from.") or not (builtin_import(x, a) or a.kids[1].s == "typing_extensions"):
                return False
    return accel_try(st)


def surely_binds(st: Node, out: dict[str, bool], bound: dict[str, bool], deep: bool = True) -> None:
    # the names statement st binds for sure once it has run, at its own level and in a with block
    # (not in its other blocks); a del, also in those blocks, removes the names it may delete from
    # out and bound. Not deep: the statements in st's blocks have been through it already, with
    # the same bound (Loader.imports), so only a with block's are looked at again (for out)
    if st.kind != "for" and not (st.kind == "annassign" and len(st.kids) < 3):
        targets(st, out, False)  # (a := may not run: and, or, an if-else's arm)
    gone: dict[str, bool] = {}
    if st.kind == "import":
        for a in st.kids:
            if a.s != "*":
                out[a.s] = True
    elif st.kind == "def" or st.kind == "class" or st.kind == "subclass":
        out[st.s] = True
    elif st.kind == "with":
        for s in st.kids[-1].kids:
            surely_binds(s, out, bound)
    else:
        deleted([st] if deep or st.kind == "del" else [], gone)
    for nm in gone:
        for d in [out, bound]:
            if nm in d:
                del d[nm]


def specials(m: Mod, body: list[Node], top: int, sure: bool = False) -> None:
    # the names module m's code (body; top: the index of the top-level statement it is in, or -1 for
    # the top level; sure: the body of an optional import of builtin modules there) binds by the
    # imports special_import() recognizes, with what they bind, "" if two differ (Mod.spec), and the
    # top-level statement with the first that binds each for sure
    for i in range(len(body)):
        st = body[i]
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            if special_import(st, a):
                t = a.kids[0].s if st.s == "" else "typing.TYPE_CHECKING"
                m.spec[a.s] = t if m.spec.get(a.s, t) == t else ""
                if (top < 0 or sure) and a.s not in m.specat:
                    m.specat[a.s] = i if top < 0 else top
        for kid in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if kid.kind == "block":
                specials(m, kid.kids, i if top < 0 else top, top < 0 and kid is st.kids[0] and builtin_try(st))
            elif kid.kind == "except":
                specials(m, kid.kids[1].kids, i if top < 0 else top)


def rebound(body: list[Node], special: bool) -> dict[str, bool]:
    # the names a module binds (but for special, by the imports special_import() recognizes), also
    # through a function's global statement: such a name is never taken for os, sys or TYPE_CHECKING
    out: dict[str, bool] = {}
    binds(body, out, special)
    for st in body:
        fns = [st] if st.kind == "def" else st.kids[0].kids if st.kind == "class" else st.kids[:0]
        for d in fns:
            if d.kind == "def":
                global_assigns(d.kids[2].kids, out, True)
    return out


def false_flag(body: list[Node]) -> int:
    # the index of module code body's top-level TYPE_CHECKING = False (the idiom that spares
    # importing typing), if no other statement binds or deletes TYPE_CHECKING, no star import may
    # and no global statement names it (no function rebinds it): module code after it, outside
    # class bodies, tests a constant False there (Loader.decide()); else -1. Code that assigns it
    # through the module, as another module's or its own after it imports itself, may assign only
    # False (Gen.store_name()) and may not delete it (Gen.del_name())
    at = -1
    for i in range(len(body)):
        st = body[i]
        if at < 0 and st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s == "TYPE_CHECKING" and st.kids[1].kind == "False":
            at = i
    names: dict[str, bool] = {}
    binds(body[:at] + body[at + 1 :] if at >= 0 else [], names, True)
    return at if at >= 0 and "TYPE_CHECKING" not in names and "*" not in names and not declares(body, "TYPE_CHECKING") else -1


def sole_binding(body: list[Node], at: int, name: str) -> bool:
    # is body[at], a top-level statement of module code body, the only one that binds or deletes
    # name, where no star import may and no global statement names it (no function rebinds it)
    names: dict[str, bool] = {}
    binds(body[:at] + body[at + 1 :], names, True)
    return name not in names and "*" not in names and not declares(body, name)


def declares(body: list[Node], name: str) -> bool:
    # does a global statement in body, also in the functions and classes it defines, name name
    for st in body:
        if (st.kind == "global" and refers(st, name)) or declares(st.kids, name):
            return True
    return False


def own_specials(d: Node) -> Mod:
    # what def d binds by its own imports that special_import() recognizes (Mod.spec, as specials()
    # finds it), and its other names: its parameters, globals and what it binds otherwise
    # (Mod.rebound)
    f = Mod("", "", "")
    body = d.kids[2].kids
    specials(f, body, -1)
    binds(body, f.rebound, False)
    globals_deep(body, f.rebound)
    for p in d.kids[0].kids:
        f.rebound[p.s] = True
    return f


def scope_names(st: Node) -> dict[str, bool]:
    # the names a def (its parameters and what its body binds, but its globals) or a class body binds
    # in its own scope, where they hide the module's names
    out: dict[str, bool] = {}
    body = st.kids[2].kids if st.kind == "def" else st.kids[0].kids
    decl: dict[str, bool] = {}
    if st.kind == "def":
        for p in st.kids[0].kids:
            out[p.s] = True
        globals_in(body, decl)
    binds(body, out, True)
    for x in body:
        bound_in(x, out)
    for nm in decl:
        if nm in out:
            del out[nm]
    return out


def bound_in(n: Node, out: dict[str, bool]) -> None:
    # the names that code n binds by :=, also in its comprehensions, by a match statement's captures
    # or by a type statement (not in the functions, classes and lambdas it defines): the compiler
    # rejects these, but in code that is dropped they still make the names local
    if n.kind == "walrus" or n.kind == "typealias" or n.kind == "pattern":
        for nm in n.s.split():
            out[nm] = True
    for k in n.kids if n.kind != "def" and n.kind != "class" and n.kind != "subclass" and n.kind != "lambda" else n.kids[:0]:
        bound_in(k, out)


def targets(st: Node, out: dict[str, bool], walrus: bool = True) -> None:
    # the names statement st assigns itself (not in its blocks), with walrus those its := bind
    k = st.kind
    if k == "assign" or k == "annassign" or k == "augassign" or k == "for" or k == "compfor" or k == "with":
        names: list[str] = []
        if k == "with":
            for it in st.kids[:-1]:
                if len(it.kids) == 2:
                    names_in(it.kids[1], names)
        for i in range(len(st.kids) - 1 if k == "assign" else 0 if k == "with" else 1):
            names_in(st.kids[i], names)
        for nm in names:
            out[nm] = True
    if walrus:
        stmt_walrus(st, out)


def collect(body: list[Node], out: dict[str, bool]) -> None:
    # Python's rule: a name assigned anywhere in a function is local to it (except ... as e too),
    # but in the defs and classes in it, scopes of their own
    for st in body:
        targets(st, out)
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        for kid in st.kids:
            if kid.kind == "block":
                collect(kid.kids, out)
            elif kid.kind == "except":
                if kid.s != "":
                    out[kid.s] = True
                collect(kid.kids[1].kids, out)

def mark(names: list[str], sure: dict[str, bool], maybe: dict[str, bool], added: list[str]) -> None:
    # names are bound: added gets those that were not surely bound
    for nm in names:
        maybe[nm] = True
        if nm not in sure:
            sure[nm] = True
            added.append(nm)


def calls(n: Node, m: Mod) -> bool:
    # may statement n call a function of module m when it runs: it names one, or a class (a
    # decorator too), apart from the bodies of the functions it defines
    k = m.kinds.get(n.s.split(".")[0], "") if n.kind == "name" or n.kind == "deco" else ""
    if k == "f" or k == "c" or k.startswith("a:" + m.q):
        return True
    for x in n.kids:
        if not (n.kind == "def" and x.kind == "block") and calls(x, m):
            return True
    return False


def top_bindings(body: list[Node]) -> dict[str, int]:
    # how many module-level statements bind each name
    count: dict[str, int] = {}
    for st in body:
        names: dict[str, bool] = {}
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass" or st.kind == "typealias":
            names[st.s] = True
        elif st.kind != "import":
            collect([st], names)
        for a in st.kids if st.kind == "import" else []:
            names[a.s] = True
        for nm in names:
            count[nm] = count.get(nm, 0) + 1
    return count


def constant_writes(n: Node, count: dict[str, int]) -> None:
    # Count every binding in the qualified program, including module-attribute stores in other
    # modules. Local bindings with the same spelling as a main-module name conservatively count
    # too. A global declaration or deletion excludes a name even without an accompanying store.
    names: dict[str, bool] = {}
    targets(n, names, False)  # (this traversal counts each walrus node itself, once)
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "except" or n.kind == "walrus" or n.kind == "typealias":
        if n.s != "":
            names[n.s] = True
    if n.kind == "global" or n.kind == "import":
        for k in n.kids:
            names[k.s] = True
    if n.kind == "del":
        gone: list[str] = []
        for k in n.kids:
            names_in(k, gone)
        for nm in gone:
            names[nm] = True
    for nm in names:
        count[nm] = count.get(nm, 0) + 1
    for k in n.kids:
        constant_writes(k, count)


def module_ints(mods: list[Mod], at: dict[str, int]) -> dict[str, str]:
    # Only a single, direct module-level assignment of an int literal, or a from-import of
    # another such name, qualifies. Keep the stores and all flow checks: the literal replaces
    # the value load only, so a read before initialization still raises the usual error.
    count: dict[str, int] = {}
    for m in mods:
        constant_writes(m.body, count)
    out: dict[str, str] = {}
    copies: list[Node] = []
    for m in mods:
        for st in m.body.kids:
            if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name" or count.get(st.kids[0].s, 0) != 1:
                continue
            e = st.kids[1]
            val = e.s if e.kind == "int" else ""
            if e.kind == "unary" and (e.s == "-" or e.s == "+") and e.kids[0].kind == "int":
                val = ("-" if e.s == "-" else "") + e.kids[0].s
            if val != "" and int_fits(val):
                out[st.kids[0].s] = val
                at[st.kids[0].s] = st.line
            elif st.s == "from" and e.kind == "name":
                copies.append(st)
    more = True
    while more:
        more = False
        for st in copies:
            nm = st.kids[0].s
            if nm not in out and st.kids[1].s in out:
                out[nm] = out[st.kids[1].s]
                at[nm] = st.line
                more = True
    return out


def module_strs(mods: list[Mod], tuples: dict[str, list[str]]) -> dict[str, str]:
    # The module globals that one direct module-level assignment binds to a str literal, or a
    # from-import of another such name: their text, which str.format() of the name reads as
    # a literal format (Gen.str_format). The name is still read, with its usual checks. Those
    # bound so to a tuple of str literals go to tuples, with its items: the attribute names
    # functools.wraps()'s assigned gives (Gen.wrap_names: WRAPPER_ASSIGNMENTS)
    count: dict[str, int] = {}
    for m in mods:
        constant_writes(m.body, count)
    out: dict[str, str] = {}
    copies: list[Node] = []
    for m in mods:
        for st in m.body.kids:
            if not ((st.kind == "assign" and len(st.kids) == 2) or (st.kind == "annassign" and len(st.kids) == 3)) or st.kids[0].kind != "name" or count.get(st.kids[0].s, 0) != 1:
                continue
            if st.kids[-1].kind == "str":
                out[st.kids[0].s] = st.kids[-1].s
            elif st.kids[-1].kind == "tuple" and all(x.kind == "str" for x in st.kids[-1].kids):
                tuples[st.kids[0].s] = [x.s for x in st.kids[-1].kids]
            elif st.kind == "assign" and st.s == "from" and st.kids[1].kind == "name":
                copies.append(st)
    more = True
    while more:
        more = False
        for st in copies:
            if st.kids[0].s not in out and st.kids[1].s in out:
                out[st.kids[0].s] = out[st.kids[1].s]
                more = True
            if st.kids[0].s not in tuples and st.kids[1].s in tuples:
                tuples[st.kids[0].s] = tuples[st.kids[1].s]
                more = True
    return out
def reads_builtin(n: Node, name: str, listed: bool, hidden: bool, mods: dict[str, bool]) -> bool:
    # may code n read builtin name (iter or next): a name node that no scope around it binds
    # (hidden: one does; a class body's or a comprehension's own names do not hide it here),
    # name of the builtins module (mods: the names that import it) or from builtins import name.
    # Not iter where an __iter__ annotated -> Iterator[T] returns iter(x) (listed, see
    # Gen.iter_ret), which steps through a list rather than making an iterator object
    k = n.kind
    if k == "name":
        return n.s == name and not hidden
    if k == "attr" and n.s == name and n.kids[0].kind == "name" and n.kids[0].s in mods:
        return True
    if k == "import":
        return len([a for a in n.kids if a.kids[0].s == "builtins." + name]) > 0
    if k == "def" and n.s == "__iter__" and name == "iter":
        a = n.kids[1]
        t = a.s if a.kind == "str" else ""
        if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr"):
            t = a.kids[0].s + "["
        t = t[: t.find("[")] if "[" in t else ""
        t = t[t.rfind(".") + 1 :]
        listed = (t == "Iterator" or t == "Iterable") and not other_return(n.kids[2])
    elif k == "def" or k == "lambda":
        listed = False
    if listed and k == "return" and len(n.kids) == 1 and n.kids[0].kind == "call" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == "iter":
        c = n.kids[0]
        return reads_builtin(c, name, False, hidden, mods) if len(c.kids) != 2 else reads_builtin(c.kids[1], name, listed, hidden, mods)
    inner = hidden  # (of a function's body; its defaults, annotations and decorators run outside)
    if k == "def" and hidden:
        decl: dict[str, bool] = {}
        globals_in(n.kids[2].kids, decl)
        inner = name not in decl  # (global name: the module's, which may not bind it)
    elif k == "def":
        inner = name in scope_names(n)
    elif k == "lambda" and not hidden:
        inner = len([p for p in n.kids[0].kids if p.s == name]) > 0
    for i in range(len(n.kids)):
        body = (k == "def" and i == 2) or (k == "lambda" and i == 1)
        if reads_builtin(n.kids[i], name, listed, inner if body else hidden, mods):
            return True
    return False


def module_reads(body: Node, name: str) -> bool:
    # may a module's code read builtin name (reads_builtin)? A module-level binding of the name,
    # also by a function's global statement, is what the module's code reads (Gen.bound)
    top: dict[str, bool] = {name: True}  # (where no name node is the name: no scope reads it so)
    if mentions(body, [name]):
        top = {}
        binds(body.kids, top, True)
        fn_globals(body, top)
    mods: dict[str, bool] = {}
    builtins_names(body, mods)
    return reads_builtin(body, name, False, name in top, mods)


def range_values(n: Node, fine: int) -> bool:
    # may code n use the builtin range as a value, an object of lib's class (Loader.program)? Any
    # read of the name may, but the callee of a range(...) that the compiler steps through itself:
    # the iterable of a for loop or of a comprehension's for clause, after a single in or not in,
    # a consumer's argument (RANGE_TAKERS, RANGE_METHODS), a starred item of a list or tuple
    # display, the value of a starred target or a list slice, yield from's, and also reversed()'s
    # there and that of map() or filter() of one iterable there. fine: n is in such a place (2: a
    # generator expression's first iterable, where a reversed() would be a value); a string
    # annotation that names range may use it. (A false True only loads the module, a false False
    # leaves range() its old error.) Only reading the tree, it makes nothing
    k = n.kind
    if k == "name":
        return n.s == "range"
    kids = n.kids
    if k == "str":
        return fine < 0 and "range" in n.s  # (an annotation's text)
    if k == "call" and kids[0].kind == "name" and kids[0].s == "range":
        if fine <= 0:
            return True
        for i in range(1, len(kids)):
            if range_values(kids[i], 0):
                return True
        return False
    how = 0  # (the call's arguments where range(...) is no value, as RANGE_TAKERS says, or 4: the
    # first, 5: the second at level 2)
    if k == "call" and kids[0].kind == "attr":
        how = RANGE_METHODS.get(kids[0].s, 0)
    elif k == "call" and kids[0].kind == "name":
        f = kids[0].s
        how = RANGE_TAKERS.get(f, 0)
        if fine == 1 and f == "reversed" and len(kids) == 2:
            how = 4
        elif fine == 1 and (f == "map" or f == "filter") and len(kids) == 3:
            how = 5
    if how != 0:
        npos = 0
        for i in range(1, len(kids)):
            if kids[i].kind != "kw" and kids[i].kind != "starred" and kids[i].kind != "dstar":
                npos += 1
        if range_values(kids[0], 0):
            return True
        at = 0
        for i in range(1, len(kids)):
            a = kids[i]
            ok = 0
            if a.kind != "kw" and a.kind != "starred" and a.kind != "dstar":
                at += 1
                if how == 3 or ((how == 1 or how == 4 or (how == 2 and npos == 1)) and at == 1):
                    ok = 1
                elif how == 5 and at == 2:
                    ok = 2
            if range_values(a, ok):
                return True
        return False
    for i in range(len(kids)):
        x = kids[i]
        ok = -1 if fine < 0 else 0  # (the rest of an annotation)
        if (k == "for" and i == 1) or (k == "compfor" and n.s == "" and i == 1) or (k == "yield" and n.s == "from"):
            ok = 1
        elif k == "listcomp" and n.s != "async" and i == 2:
            ok = 2 if n.s == "gen" else 1
        elif k == "cmp" and (n.s == "in" or n.s == "not in") and i == 1:
            ok = 1
        elif k == "assign" and len(kids) == 2 and i == 1 and (kids[0].kind == "slice" or starred_target(kids[0])):
            ok = 1
        elif ((k == "param" or k == "starparam" or k == "dstarparam") and i == 0) or (k == "def" and i == 1) or (k == "annassign" and i == 1):
            ok = -1  # (an annotation)
        elif (k == "list" or k == "tuple") and x.kind == "starred":
            if range_values(x.kids[0], 1):
                return True
            continue
        if range_values(x, ok):
            return True
    return False


def builtins_names(n: Node, out: dict[str, bool]) -> None:
    # the names that an import of the builtins module in n binds (import builtins as b)
    for a in n.kids if n.kind == "import" and n.s == "" else n.kids[:0]:
        if a.kids[0].s == "builtins":
            out[a.s] = True
    for k in n.kids:
        builtins_names(k, out)


def needs_eh(body: list[Node]) -> bool:
    # does body need exception handling or with-file cleanup, also in the functions and classes
    # it defines (a class with bases is a subclass node whose first kid is the class)
    for st in body:
        if st.kind == "try" or st.kind == "with":
            return True
        for kid in st.kids if st.kind != "subclass" else st.kids[0].kids:
            if kid.kind == "block" and needs_eh(kid.kids):
                return True
    return False


def defines(n: Node, name: str) -> bool:
    # does code n define a function name anywhere (also in the functions and classes it defines)
    if n.kind == "def" and n.s == name:
        return True
    for k in n.kids:
        if defines(k, name):
            return True
    return False


def name_nodes(n: Node, out: dict[str, bool]) -> None:
    # the names of every name node in n
    if n.kind == "name":
        out[n.s] = True
    for k in n.kids:
        name_nodes(k, out)


def calls_init(n: Node) -> bool:
    # does n hold a call of an __init__ method (outside the functions and classes it defines)
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s == "__init__":
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if calls_init(k):
            return True
    return False


def reads(n: Node, name: str) -> bool:
    # does code n read name in its own scope where it may run: not after a return, raise, break or
    # continue of its block, as a list comprehension's own variable, in an annotation, which a
    # function does not evaluate, or in the functions and classes it defines
    k = n.kind
    if k == "name":
        return n.s == name
    if k == "def" or k == "class" or k == "subclass" or k == "lambda":
        return False
    if k == "listcomp":
        names: list[str] = []
        comp_names(n, names)
        if name in names:
            return reads(n.kids[2], name)
    for i in range(len(n.kids)):
        if not (k == "annassign" and i == 1) and reads(n.kids[i], name):
            return True
        x = n.kids[i].kind
        if k == "block" and (x == "return" or x == "raise" or x == "break" or x == "continue"):
            return False
    return False


def read_names(n: Node, out: dict[str, bool]) -> None:
    # every name that reads(n, name) finds, in one walk of n
    k = n.kind
    if k == "name":
        out[n.s] = True
        return
    if k == "def" or k == "class" or k == "subclass" or k == "lambda":
        return
    names: list[str] = []
    if k == "listcomp":
        comp_names(n, names)
    for i in range(len(n.kids)):
        if k == "listcomp" and i != 2:
            # (a name its targets bind counts only in its first iterable)
            inner: dict[str, bool] = {}
            read_names(n.kids[i], inner)
            for nm in inner:
                if nm not in names:
                    out[nm] = True
        elif not (k == "annassign" and i == 1):
            read_names(n.kids[i], out)
        x = n.kids[i].kind
        if k == "block" and (x == "return" or x == "raise" or x == "break" or x == "continue"):
            return


def local_types(body: list[Node], out: dict[str, Node]) -> None:
    # a type for the names a function's body binds (not in the functions and classes it defines):
    # the annotation of one, or the type of a constant one is assigned
    for st in body:
        v = st.kids[-1] if st.kind == "assign" else st
        if v.kind == "unary" and v.s == "-":
            v = mk("int", "", v.line, []) if v.kids[0].kind == "True" or v.kids[0].kind == "False" else v.kids[0]  # (-True is -1)
        t = v.kind if v.kind == "int" or v.kind == "float" or v.kind == "str" else "bool" if v.kind == "True" or v.kind == "False" else ""
        for x in st.kids[:-1] if st.kind == "assign" and t != "" else st.kids[:0]:
            if x.kind == "name" and x.s not in out:
                out[x.s] = mk("name", t, st.line, [])
        if st.kind == "annassign" and st.kids[0].kind == "name" and st.kids[0].s not in out:
            out[st.kids[0].s] = st.kids[1]
        for kid in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if kid.kind == "block":
                local_types(kid.kids, out)
            elif kid.kind == "except":
                local_types(kid.kids[1].kids, out)


def refers(n: Node, name: str) -> bool:
    # does n read name (outside the functions and classes it defines)
    if n.kind == "name" and n.s == name:
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if refers(k, name):
            return True
    return False


def first_use(n: Node, names: dict[str, bool], now: bool) -> Node | None:
    # the first name node of n that is one of names, or decorator that starts with one; with now,
    # only in the code that runs when n does: not in the bodies of the functions it defines (but
    # in their decorators, defaults and annotations, a class body, and a lambda's body, which what
    # it is given to may call)
    if (n.kind == "name" and n.s in names) or (n.kind == "deco" and n.s.split(".")[0] in names):
        return n
    for i in range(len(n.kids)):
        if not (now and n.kind == "def" and i == 2):
            r = first_use(n.kids[i], names, now)
            if r is not None:
                return r
    return None


def deferred_use(n: Node, names: dict[str, bool]) -> Node | None:
    # first_use() in the lambdas and generator expressions of the code that runs when n does (not
    # in the bodies of the functions it defines), which run when what holds them calls or
    # iterates them: then, or later
    if n.kind == "lambda" or (n.kind == "listcomp" and n.s == "gen"):
        return first_use(n, names, False)
    for i in range(len(n.kids)):
        if not (n.kind == "def" and i == 2):
            r = deferred_use(n.kids[i], names)
            if r is not None:
                return r
    return None


def all_imports(body: list[Node], out: list[str]) -> None:
    # the user modules that body imports, in its functions too
    for st in body:
        if st.kind == "uimport":
            for x in st.kids:
                out.append(x.s)
        for kid in st.kids:
            if kid.kind == "block":
                all_imports(kid.kids, out)
            elif kid.kind == "except":
                all_imports(kid.kids[1].kids, out)


def imports_user(n: Node) -> bool:
    # does code n (also in its functions and classes) import a module that is not builtin, whose
    # code, or that of the modules it imports, may run there
    for a in n.kids if n.kind == "import" else n.kids[:0]:
        if n.s.startswith("from.") or not (builtin_import(n, a) or a.kids[1].s == "typing_extensions"):
            return True
    for k in n.kids:
        if imports_user(k):
            return True
    return False


def top_imports(body: list[Node]) -> list[str]:
    # the user modules that module-level code (body, not its functions) imports
    out: list[str] = []
    for st in body:
        if st.kind == "uimport":
            for x in st.kids:
                out.append(x.s)
        elif st.kind != "def" and st.kind != "class":
            for kid in st.kids:
                if kid.kind == "block":
                    out.extend(top_imports(kid.kids))
                elif kid.kind == "except":
                    out.extend(top_imports(kid.kids[1].kids))
    return out


def deleted(body: list[Node], out: dict[str, bool], defs: bool = False) -> None:
    # the names that del statements in body unbind (not in functions), and the end of an except
    # clause that binds a name (except E as e: e is unbound after it); with defs, also those its
    # def and class statements bind
    for st in body:
        if defs and (st.kind == "def" or st.kind == "class" or st.kind == "subclass"):
            out[st.s] = True
        if st.kind == "del":
            names: list[str] = []
            for t in st.kids:
                if t.kind == "name" or t.kind == "tuple" or t.kind == "list":
                    names_in(t, names)
            for nm in names:
                out[nm] = True
        if st.kind != "def" and st.kind != "class":
            for kid in st.kids:
                if kid.kind == "block":
                    deleted(kid.kids, out, defs)
                elif kid.kind == "except":
                    if kid.s != "":
                        out[kid.s] = True
                    deleted(kid.kids[1].kids, out, defs)


def none_assigns(body: list[Node], out: dict[str, list[Node]]) -> None:
    # every value module-level code (body, not its functions) assigns to each name; a name bound
    # any other way (for, with, +=, an annotation, unpacking, :=) gets an "omit" node
    for st in body:
        k = st.kind
        if k == "assign":
            for t in st.kids[:-1]:
                names: list[str] = []
                names_in(t, names)
                for nm in names:
                    if nm not in out:
                        out[nm] = []
                    out[nm].append(st.kids[-1] if t.kind == "name" else mk("omit", "", st.line, []))
        elif k == "annassign" or k == "augassign" or k == "for" or k == "with":
            asg: dict[str, bool] = {}
            collect([st], asg)
            for nm in asg:
                if nm not in out:
                    out[nm] = []
                out[nm].append(mk("omit", "", st.line, []))
        w: dict[str, bool] = {}
        stmt_walrus(st, w)  # (x := v)
        for nm in w:
            if nm not in out:
                out[nm] = []
            out[nm].append(mk("omit", "", st.line, []))
        for kid in st.kids:
            if kid.kind == "block" and st.kind != "def" and st.kind != "class":
                none_assigns(kid.kids, out)
            elif kid.kind == "except":
                if kid.s != "":
                    if kid.s not in out:
                        out[kid.s] = []
                    out[kid.s].append(mk("omit", "", kid.line, []))
                none_assigns(kid.kids[1].kids, out)


def lambda_def(n: Node) -> Node:
    # lambda n as the def it is (def <lambda>(params): return body): a new node around n's own
    # parameters and body, so that what is marked on those (Node.chk) is n's
    return mk("def", "<lambda>", n.line, [n.kids[0], mk("noann", "", n.line, []), mk("block", "", n.line, [mk("return", "", n.line, [n.kids[1]])])])


def free_reads(n: Node, bound: dict[str, bool], out: dict[str, bool]) -> None:
    # the names that code n reads where it runs, but those in bound: of the defs and lambdas in it,
    # the names they take from around them (closure_free), and in a comprehension those it does not
    # bind itself; a variable's annotation, which a function never evaluates, is not read
    k = n.kind
    if k == "name":
        if n.s not in bound:
            out[n.s] = True
        return
    if k == "def" or k == "lambda":
        # (its defaults, and a def's annotations and decorators, are evaluated where it is)
        for p in n.kids[0].kids:
            free_reads(p.kids[1], bound, out)
            free_reads(p.kids[0], bound, out)
        for x in n.kids[1:2] + n.kids[3:] if k == "def" else n.kids[:0]:
            if x.kind == "deco":
                root = x.s[: x.s.find(".")] if "." in x.s else x.s
                if root not in bound:
                    out[root] = True
            free_reads(x, bound, out)
        inner: dict[str, bool] = {}
        closure_free(n if k == "def" else lambda_def(n), inner)
        for nm in inner:
            if nm not in bound:
                out[nm] = True
        return
    if k == "listcomp":
        free_reads(n.kids[2], bound, out)
        own = dict(bound)
        names: list[str] = []
        comp_names(n, names)
        for nm in names:
            own[nm] = True
        for i in range(len(n.kids)):
            if i != 1 and i != 2:
                free_reads(n.kids[i], own, out)
        return
    if k == "annassign":
        for x in n.kids[2:]:
            free_reads(x, bound, out)
        if n.kids[0].kind != "name":
            free_reads(n.kids[0], bound, out)
        return
    if k == "global" or k == "nonlocal" or k == "class" or k == "subclass":
        return
    for kid in n.kids:
        free_reads(kid, bound, out)


def target_unbound(t: Node, names: list[str], bound: list[str]) -> str:
    # the first of names that assigning to target t reads (in an attribute's object, or in a
    # subscript) before a name it binds is bound, or "": bound has the names bound so far, and
    # gets t's own, in the order t assigns them (left to right)
    k = t.kind
    if k == "name":
        bound.append(t.s)
        return ""
    if k == "tuple" or k == "list" or k == "starred":
        for x in t.kids:
            nm = target_unbound(x, names, bound)
            if nm != "":
                return nm
        return ""
    out: dict[str, bool] = {}
    for x in t.kids:
        free_reads(x, {}, out)
    for nm in names:
        if nm in out and nm not in bound:
            return nm
    return ""


def comp_unbound(c: Node, names: list[str]) -> str:
    # why comprehension c, whose variables are names, is not supported, or "": a clause (a
    # condition, a later for clause's iterable, or a for clause's target) reads one of them that
    # only that clause's target or a later one binds, which CPython finds unbound (UnboundLocalError)
    bound: list[str] = []
    nm = target_unbound(c.kids[1], names, bound)
    for x in c.kids[3:] if len(c.kids) > 3 and (c.kids[3].kind == "compfor" or c.kids[3].kind == "compif") else c.kids[:0]:
        if nm != "":
            break
        out: dict[str, bool] = {}
        free_reads(x.kids[1] if x.kind == "compfor" else x.kids[0], {}, out)
        for v in names:
            if v in out and v not in bound and nm == "":
                nm = v
        if nm == "" and x.kind == "compfor":
            nm = target_unbound(x.kids[0], names, bound)
    return "" if nm == "" else f"'{nm}' is read before the comprehension's for clause that binds it, where CPython raises UnboundLocalError (not supported)"


def comp_shared(c: Node, j: int, out: list[str]) -> None:
    # the names that comprehension c's later for clause c.kids[j] binds into the variable of the
    # latest earlier for clause that binds them too, as CPython's comprehension has one variable of
    # each name: those that a clause between the two (or this one's target) reads once a loop
    # between them has run, where it can see this clause's value. Elsewhere this clause's value
    # can go to a new variable, which may have another type
    mine: list[str] = []
    names_in(c.kids[j].kids[0], mine)
    for nm in mine:
        q = -1  # (2: the first for clause, whose iterable is c.kids[2])
        first: list[str] = []
        names_in(c.kids[1], first)
        if nm in first:
            q = 2
        for i in range(3, j):
            b: list[str] = []
            if c.kids[i].kind == "compfor":
                names_in(c.kids[i].kids[0], b)
            if nm in b:
                q = i
        if q < 0 or nm in out:
            continue
        loop = False
        for i in range(q + 1, j + 1):
            x = c.kids[i]
            rd: dict[str, bool] = {}
            free_reads(x.kids[1] if x.kind == "compfor" else x.kids[0], {}, rd)
            if (loop and nm in rd) or (x.kind == "compfor" and target_unbound(x.kids[0], [nm], []) != ""):
                out.append(nm)
                break
            loop = loop or x.kind == "compfor"


def closure_free(d: Node, out: dict[str, bool]) -> None:
    # the names that def d (also a lambda's, lambda_def) takes from the scopes around it: those it
    # reads and does not bind itself, and those it declares nonlocal (not those it declares global)
    loc: dict[str, bool] = {}
    decl: dict[str, str] = {}
    for p in d.kids[0].kids:
        loc[p.s] = True
    scope_binds(d.kids[2].kids, loc, decl)
    for nm in decl:
        loc[nm] = True
        if decl[nm] == "nonlocal":
            out[nm] = True
    for st in d.kids[2].kids:
        free_reads(st, loc, out)


def nested_defs(n: Node, out: list[Node]) -> None:
    # the defs and lambdas that code n defines itself (not those inside them)
    if n.kind == "def" or n.kind == "lambda":
        out.append(n)
        for p in n.kids[0].kids:
            nested_defs(p.kids[1], out)  # (a lambda among the defaults is defined where n is)
        return
    if n.kind == "class" or n.kind == "subclass":
        return
    for k in n.kids:
        nested_defs(k, out)


def appends_to(st: Node) -> bool:
    # is statement st x = x + e
    if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name":
        return False
    v = st.kids[1]
    return v.kind == "binop" and v.s == "+" and v.kids[0].kind == "name" and v.kids[0].s == st.kids[0].s


def str_appends(body: list[Node], out: dict[str, bool]) -> None:
    # the names that the statements of a function's body append to: x += e, x = x + e
    # (Gen.str_append, where x is a str local), also in its blocks (not in its defs and classes):
    # statements alone, which only blocks and except clauses hold, as for globals_in
    for st in body:
        if (st.kind == "augassign" and st.s == "+" and st.kids[0].kind == "name") or appends_to(st):
            out[st.kids[0].s] = True
        elif st.kind != "def" and st.kind != "class" and st.kind != "subclass":
            for kid in st.kids:
                if kid.kind == "block":
                    str_appends(kid.kids, out)
                elif kid.kind == "except":
                    str_appends(kid.kids[1].kids, out)


def lambda_flags(n: Node, inlam: bool, out: dict[str, bool]) -> None:
    # the names that the lambdas in code n read (all its reads, if inlam: n is in one) whose flag is
    # one of the function's (Node.mchk, L: an import in a try statement of it binds them): a lambda
    # reads them where it runs, and so takes their flags' cells. Not those of a def in n, whose
    # imports are its own, but those of its defaults and decorators, which run where it is
    if n.kind == "def" or n.kind == "lambda":
        for p in n.kids[0].kids:
            lambda_flags(p.kids[1], inlam, out)
        for x in n.kids[3:] if n.kind == "def" else n.kids[1:]:
            lambda_flags(x, inlam or n.kind == "lambda", out)
        return
    if inlam and n.mchk.split(";")[0].endswith(" L"):
        out[n.mchk.split(" ")[0]] = True
    for k in n.kids:
        lambda_flags(k, inlam, out)


def nonlocal_decls(n: Node, out: dict[str, bool]) -> None:
    # the names that nonlocal statements in code n declare, also in the defs and lambdas in it
    if n.kind == "nonlocal":
        for x in n.kids:
            out[x.s] = True
    for k in n.kids:
        nonlocal_decls(k, out)


def stack_aliases(n: Node, names: dict[str, bool]) -> bool:
    # adds to names each local that an assignment in code n (not in its defs and lambdas) gives a
    # name of names (y = args), and says whether it added one
    added = False
    if n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[1].kind == "name" and n.kids[1].s in names and n.kids[0].s not in names:
        names[n.kids[0].s] = True
        added = True
    if n.kind == "def" or n.kind == "lambda" or n.kind == "class":
        return added
    for k in n.kids:
        if stack_aliases(k, names):
            added = True
    return added


def stack_kept(n: Node, names: list[str]) -> bool:
    # whether code n could keep what a name of names holds where the copy before each statement
    # (Gen.keep_stack) does not look: in a generator (yield, await), a closure (a def, lambda or
    # class that names one), a global or nonlocal, or a while loop's test, which runs again after
    # the statements of its body
    k = n.kind
    if k == "yield" or k == "await" or k == "async":
        return True
    if k == "def" or k == "lambda" or k == "class" or k == "subclass" or k == "lclass" or k == "global" or k == "nonlocal":
        return mentions(n, names)
    if k == "while" and mentions(n.kids[0], names):
        return True
    for c in n.kids:
        if stack_kept(c, names):
            return True
    return False


def chk_names(n: Node, out: dict[str, bool]) -> None:
    # the names of the reads in code n (not in the defs and lambdas in it) that Flow marked
    # (Node.chk): they may find their variable unassigned
    if n.kind == "name" and n.chk:
        out[n.s] = True
    if n.kind == "def" or n.kind == "lambda":
        return
    for k in n.kids:
        chk_names(k, out)


def local_names(body: list[Node], out: dict[str, bool]) -> None:
    # a function's locals: the names it assigns, deletes or defines (a def or class, which is an
    # error where it is compiled, as bound_in()'s are), but not a qualified name (M$x), which an
    # assignment to a module's attribute (M.x = ...) or a global M declares makes
    asg: dict[str, bool] = {}
    collect(body, asg)
    deleted(body, asg, True)
    for st in body:
        bound_in(st, asg)
    for nm in asg:
        if "$" not in nm:
            out[nm] = True


def import_reads(n: Node, sure: dict[str, bool], out: dict[str, bool], user: dict[str, bool]) -> None:
    # the names that code n of a function reads where no import in it has surely bound them yet
    # (sure: those an import before n has bound, to which n adds those it surely binds: in both
    # branches of an if, in a with block, not in a loop), and those its imports of Python modules
    # bind (user)
    if n.kind == "global":
        return  # (it names them, but reads none)
    if n.kind == "name" and n.s not in sure:
        out[n.s] = True
    if n.kind == "def":
        # Named closures do not capture import binding flags. An enclosing import they read
        # must have surely run before their definition; otherwise reject that enclosing
        # function rather than compile an unbound read as an imported value.
        free: dict[str, bool] = {}
        closure_free(n, free)
        for nm in free:
            if nm not in sure:
                out[nm] = True
    for a in n.kids if n.kind == "import" else n.kids[:0]:
        sure[a.s] = True
        if n.s.startswith("from.") or not (builtin_import(n, a) or a.kids[1].s == "typing_extensions"):
            user[a.s] = True
    if n.kind == "if":
        import_reads(n.kids[0], sure, out, user)
        then = dict(sure)
        import_reads(n.kids[1], then, out, user)
        import_reads(n.kids[2], sure, out, user)
        gone: list[str] = []
        for nm in sure:
            if nm not in then:
                gone.append(nm)
        for nm in gone:
            del sure[nm]
        if n.kids[0].kind == "True":
            for nm in then:
                sure[nm] = True
        return
    for k in n.kids if n.kind != "def" and n.kind != "class" and n.kind != "subclass" and n.kind != "lambda" else n.kids[:0]:
        import_reads(k, dict(sure) if k.kind == "block" and n.kind != "with" else sure, out, user)
    first = n.kids[0].kids[0] if n.kind == "try" and len(n.kids[0].kids) > 0 else n
    for a in first.kids if first.kind == "import" else first.kids[:0]:
        # try: import m as x / ... (or from m import x): after the statement, x is bound unless the
        # import raised, which a read of it checks as it runs (Loader.fragile, Gen.modchk)
        sure[a.s] = True


def globals_in(body: list[Node], out: dict[str, bool]) -> None:
    # the names the global statements of a function's body declare (not those of the defs and
    # classes in it, scopes of their own)
    for st in body:
        if st.kind == "global":
            for nm in st.kids:
                out[nm.s] = True
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        for kid in st.kids:
            if kid.kind == "block":
                globals_in(kid.kids, out)
            elif kid.kind == "except":
                globals_in(kid.kids[1].kids, out)


def globals_deep(body: list[Node], out: dict[str, bool]) -> None:
    # (globals_in, also in the defs inside: each may rebind a name of the module)
    for st in body:
        if st.kind == "global":
            for nm in st.kids:
                out[nm.s] = True
        for kid in st.kids:
            if kid.kind == "block":
                globals_deep(kid.kids, out)
            elif kid.kind == "except":
                globals_deep(kid.kids[1].kids, out)


def global_assigns(body: list[Node], out: dict[str, bool], imports: bool = False) -> None:
    # the names of the module that a function's body assigns (also by an import, with imports),
    # declared global, also those the defs inside it assign so (each a scope of its own: its own
    # global statements decide)
    decl: dict[str, bool] = {}
    asg: dict[str, bool] = {}
    globals_in(body, decl)
    if imports:
        binds(body, asg, True)
    else:
        collect(body, asg)
    for nm in decl:
        if nm in asg:
            out[nm] = True
    inner: list[Node] = []
    for st in body:
        nested_defs(st, inner)
    for d in inner:
        if d.kind == "def":
            global_assigns(d.kids[2].kids, out, imports)


def fn_globals(n: Node, out: dict[str, bool]) -> None:
    # the names of the module that the functions code n defines anywhere (in its blocks, classes
    # and functions too) assign, also by an import, declared global (global_assigns())
    if n.kind == "def":
        global_assigns(n.kids[2].kids, out, True)
    for k in n.kids:
        fn_globals(k, out)


def scope_globals(body: list[Node], out: dict[str, int]) -> None:
    # the names that the global statements of a scope (body: its statements) declare, not those of
    # the functions and classes it defines, each with the line of its first global statement
    for st in body:
        if st.kind == "global":
            for nm in st.kids:
                if nm.s not in out:
                    out[nm.s] = st.line
        elif st.kind != "def" and st.kind != "class" and st.kind != "subclass":
            for kid in st.kids:
                if kid.kind == "block":
                    scope_globals(kid.kids, out)
                elif kid.kind == "except":
                    scope_globals(kid.kids[1].kids, out)


def stmt_binds(st: Node, name: str) -> bool:
    # does statement st itself (not the blocks it holds) bind variable name
    k = st.kind
    names: list[str] = []
    if k == "assign":
        for t in st.kids[:-1]:
            names_in(t, names)
    elif k == "annassign" or k == "augassign" or k == "for":
        names_in(st.kids[0], names)
    elif k == "with":
        for it in st.kids[:-1]:
            if len(it.kids) == 2:
                names_in(it.kids[1], names)
    if name in names:
        return True
    w: dict[str, bool] = {}
    stmt_walrus(st, w)
    return name in w


def only_none(body: list[Node], name: str) -> bool:
    # do the statements in body (into blocks, not into defs and classes) bind variable name only
    # to None, by name = None
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        if stmt_binds(st, name) and not (st.kind == "assign" and nonexpr(st.kids[-1]) and assigns(st, name)):
            return False  # (also a, name = None, None)
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            if a.s == name:
                return False  # (import m as name, which stmt_binds() leaves out)
        for kid in st.kids:
            if kid.kind == "block" and not only_none(kid.kids, name):
                return False
            if kid.kind == "except" and not only_none(kid.kids[1].kids, name):
                return False
    return True


def bind_count(body: list[Node], name: str) -> int:
    # how many statements in body (into blocks, not into defs and classes) bind variable name:
    # an assignment counts once, another binding (a for loop's, an import's, an except clause's,
    # a def's) twice
    n = 0
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            n += 2 if st.s == name else 0
            continue
        if stmt_binds(st, name):
            n += 1 if st.kind == "assign" else 2
        if has_kind(st, "walrus"):
            n += 2
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            n += 2 if a.s == name else 0
        for kid in st.kids:
            if kid.kind == "block":
                n += bind_count(kid.kids, name)
            if kid.kind == "except":
                n += (2 if kid.s == name else 0) + bind_count(kid.kids[1].kids, name)
    return n


def nonexpr(e: Node) -> bool:
    # is e None, or a conditional expression of None in both arms
    return e.kind == "None" or (e.kind == "ifexp" and nonexpr(e.kids[1]) and nonexpr(e.kids[2]))


def binds_other(body: list[Node], name: str) -> bool:
    # does code body bind name other than as an except clause's name (not in the functions and
    # classes it defines)
    for st in body:
        if stmt_binds(st, name) or ((st.kind == "def" or st.kind == "class" or st.kind == "subclass") and st.s == name):
            return True
        for a in st.kids if st.kind == "import" else st.kids[:0]:
            if a.s == name:
                return True
        for k in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if (k.kind == "block" and binds_other(k.kids, name)) or (k.kind == "except" and binds_other(k.kids[1].kids, name)):
                return True
    return False


def has_finally(body: list[Node]) -> bool:
    # does code body hold a try statement with a finally block (not in the functions and classes it defines)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        for k in st.kids:
            if (k.kind == "block" and ((st.kind == "try" and k.s != "else" and k is not st.kids[0]) or has_finally(k.kids))) or (k.kind == "except" and has_finally(k.kids[1].kids)):
                return True
    return False


def binds_as(body: list[Node], name: str) -> bool:
    # does an except clause in code body bind name (not in the functions and classes it defines)
    for st in body:
        for k in st.kids if st.kind != "def" and st.kind != "class" and st.kind != "subclass" else st.kids[:0]:
            if (k.kind == "block" and binds_as(k.kids, name)) or (k.kind == "except" and (k.s == name or binds_as(k.kids[1].kids, name))):
                return True
    return False


def assigns(st: Node, name: str) -> bool:
    # is name a target of assignment st itself (not inside a tuple)
    for t in st.kids[:-1]:
        if t.kind == "name" and t.s == name:
            return True
    return False


def typed_default(body: list[Node], d: Node, ret: bool) -> bool:
    # is d the default value of a get() or setdefault() call that a statement in body (into blocks)
    # returns (ret: the function returns a list or dict) or assigns to an annotated variable, so
    # that the type expected there types it (see fill)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        v = st.kids[-1] if len(st.kids) > 0 else st
        if ((st.kind == "return" and ret) or (st.kind == "annassign" and len(st.kids) == 3)) and v.kind == "call" and len(v.kids) == 3 and v.kids[2] is d:
            return v.kids[0].kind == "attr" and (v.kids[0].s == "get" or v.kids[0].s == "setdefault")
        for kid in st.kids:
            if kid.kind == "block" and typed_default(kid.kids, d, ret):
                return True
            if kid.kind == "except" and typed_default(kid.kids[1].kids, d, ret):
                return True
    return False


def aliases(n: Node, name: str) -> bool:
    # does n (outside its return statements: the callers are told, see guessed) give the container
    # that variable name holds to another variable, container, field or function, which could fill
    # it: x = name, [name], f(name), a or name; not print(name), len(name), sorted(name), for x in name
    if n.kind == "return" or n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for i in range(len(n.kids)):
        kid = n.kids[i]
        if kid.kind == "name" and kid.s == name:
            if (n.kind == "assign" or n.kind == "annassign") and i == len(n.kids) - 1 and i > 0:
                return True
            if n.kind == "call" and i > 0 and not (n.kids[0].kind == "name" and n.kids[0].s in NOREF):
                return True
            if n.kind in "kw list tuple dict boolop".split() or (n.kind == "ifexp" and i > 0):
                return True
        elif aliases(kid, name):
            return True
    return False


def shows_items(n: Node, name: str) -> bool:
    # does n (outside the functions and classes it defines) assign variable name, or fill the
    # container it holds: name[k] = v, name[a:b] = xs, name += xs, name.append(v), insert,
    # extend, setdefault, get, and a set's add and update
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    if stmt_binds(n, name):
        return True
    if n.kind == "assign":
        for t in n.kids[:-1]:
            if (t.kind == "index" or t.kind == "slice") and t.kids[0].kind == "name" and t.kids[0].s == name:
                return True
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name:
        if n.kids[0].s in "append insert extend setdefault get add update".split():
            return True
    for k in n.kids:
        if shows_items(k, name):
            return True
    return False
