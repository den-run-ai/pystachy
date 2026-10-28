"""Exceptions component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import (
    binds_as,
    binds_other,
    collect,
    deleted,
    globals_in,
    has_finally,
    reads,
)
from src.pystachy_compiler.diagnostics import dynamic_program, shown
from src.pystachy_compiler.ir import Data, Exit, FnInfo, Ins, Try, Val
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.specs import (
    BIG,
    BIGOPT,
    EXCBASES,
    FROZENERR,
    EXCEPTIONS,
    EXCKW,
    PYBUILTINS,
    exc_base_of,
    exc_derives,
    is_excname,
)
from src.pystachy_compiler.syntax import NOKIDS, Node, mk
from src.pystachy_compiler.utils import (
    is_const,
    is_opt,
    is_sopt,
    is_tuple,
    is_union,
    meet,
    numeric_identity,
    pure_arg,
    targs,
    tname,
    typestr,
    umembers,
    unopt,
)


def gen_try_(self, n: Node) -> None:
    # try: B / except C1 as e: H1 / ... / else: L / finally: F. An exception raised in B goes to
    # the landing block of the except clauses (hE), one raised in a clause or L to that of F
    # (hF): from a call that may raise through the unwinder (an invoke), from a raise of this
    # function directly (see eh_ir). hE tests the clauses in order (exc.match) and throws again
    # what none catches; hF runs a copy of F and throws again. B and L, and each clause that
    # ends, go on to one copy of F; a break, continue or return out of the statement runs one
    # of its own (see leave), as CPython compiles F once for each way out. A clause whose name
    # may be read after it has a landing block of its own, which unbinds the name
    if n.s == "*":
        self.err("'except*' is not supported")
    hs: list[Node] = []
    orelse: list[Node] = []
    fin: list[Node] = []
    hasfin = False
    for k in n.kids[1:]:
        if k.kind == "except":
            k.kids[0] = self.clause_or(k.kids[0])
            hs.append(k)
        elif k.s == "else":
            orelse = k.kids
        else:
            fin = k.kids
            hasfin = True
    sets = [self.catches(h) for h in hs]
    self.line = n.line
    # what narrowed holds (see narrow_by) where an exception may come from: in a clause, what
    # held before the statement but for the names B binds; in F on the way out of an
    # exception, but for those that B, L and the clauses bind; after the statement, what holds
    # at the end of each way that goes on (ends)
    hst = self.unnarrowed([n.kids[0].kids])
    fst = self.unnarrowed([n.kids[0].kids, orelse] + [h.kids[1].kids for h in hs])
    ends: list[dict[str, str]] = []
    # the try notes the depth of the unwind actions (pys_exc_begin runs those added since) and
    # the exception being handled, which every way out of its clauses restores
    mark = Val(self.rt("pys_try_mark", "i64", []), "int")
    if self.fn.gbase != "":
        mark = Val(self.scalar('sub', [mark, Val(self.mload('int', self.fn.gbase), 'int')]), "int")  # (see landing)
    old = self.exc_mark()
    slot = self.alloca("exc", "")
    outer = self.handler
    he = self.label() if len(hs) > 0 else ""
    hf = self.label() if hasfin else ""
    done = self.label()
    tr = Try(self.label())
    tr.landing = he
    tr.final = hf
    tr.exit = done
    self.fn.tries.append(tr)
    self.branch += 1
    fx = Exit("finally", "", outer)
    if hasfin:
        fx.body = fin
        fx.nloops = len(self.loops)
        fx.nexcs = len(self.excs)
        if has_finally(fin):
            # a finally block that holds one: compiled once, after the rest of the statement,
            # where each way out stores its index and jumps (leave), else the copies of copies
            # would grow exponentially with the nesting (CPython's bytecode does)
            fx.entry = self.label()
            fx.sel = self.alloca("int", "")
        self.exits.append(fx)
    self.handler = he if he != "" else hf
    self.place(tr.body)
    self.stmts(n.kids[0].kids)
    self.handler = hf if hasfin else outer
    if len(orelse) > 0 and not (self.term and self.curfn.inst):
        tr.orelse = self.label()
        self.place(tr.orelse)
        self.stmts(orelse)
    live = not self.term  # (does any path go on to done)
    if live:
        ends.append(self.narrowed)
    self.br(done)
    if he != "":
        e = self.landing(he, slot, mark)
        nxt = ""
        for j in range(len(hs)):
            h = hs[j]
            self.line = h.line
            if h.s != "" and not self.modlevel and h.s in self.gdecl:
                self.err(f"except ... as {h.s}, of the global '{h.s}', in a function is not supported: the end of the clause deletes the global, as del would")
            for c in h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]] if h.kids[0].kind == "name" else NOKIDS:
                self.modchk(c)  # (read through an import that may have raised)
                if (c.chk or self.foreign(c.s)) and c.s in self.gflag and c.s in self.classes:
                    # a class whose class statement may not have run yet
                    self.guard(self.scalar('xor', [Val(self.mload('bool', f'@g.{c.s}.def'), 'bool'), Val('true', 'bool')]), self.unbound(c.s))
            if sets[j] != "":
                l = self.label()
                nxt = self.label()
                self.cbr(self.exc_match(e, sets[j]), l, nxt)
                self.place(l)
            self.narrowed = dict(hst)
            if h.s != "":
                self.bind_as(h.s, e, self.as_type(h))
            x = Exit("handler", old, self.handler)
            x.name = h.s
            up = self.handler
            hu = ""
            if h.s != "" and self.unbinds(h.s) and up != "":
                # an exception that leaves the clause unbinds its name too, where something may
                # read it after (CPython deletes it in a finally block of its own): the clause
                # has a landing block of its own, which unbinds the name and throws again (an
                # imported module's code is in a landing block's region, see function)
                hu = self.label()
                self.handler = hu
                self.place(self.label())
            self.exits.append(x)
            self.excs.append(e)
            self.stmts(h.kids[1].kids)
            self.excs.pop()
            self.exits.pop()
            if not self.term:
                self.exc_back(old)
                self.unbind(h.s)
                live = True
                ends.append(self.narrowed)
                self.br(done)
            self.handler = up
            if hu != "":
                ue = self.landing(hu, slot, mark)
                self.unbind(h.s)
                self.throw(ue)
            if len(self.shadows) > 0 and self.shadows[-1][0] == h.s:
                self.unshadow()
            if sets[j] == "":
                nxt = ""
                break  # (it catches everything: the clauses after it never run)
            self.place(nxt)
        if nxt != "":
            self.throw(e)
    if hasfin:
        self.exits.pop()
        self.handler = outer
        e = self.landing(hf, slot, mark)
        if fx.entry != "":
            # (the exception goes on after the finally block, from a slot of its own)
            sl = self.alloca("exc", "")
            self.mstore('%ptr', e.v, sl)
            self.mstore('int', f'{len(fx.conts)}', fx.sel)
            fx.conts.append(self.label())
            self.br(fx.entry)
            self.place(fx.conts[-1])
            self.throw(Val(self.mload('%ptr', sl), "exc"))
        else:
            self.exits.append(Exit("handler", old, outer))  # (a break or return in F drops the exception)
            self.excs.append(e)
            self.narrowed = dict(fst)
            self.stmts(fin)
            self.excs.pop()
            self.exits.pop()
            if not self.term:
                self.throw(e)
    self.handler = outer
    self.branch -= 1
    if live and fx.entry != "":
        self.place(done)
        self.mstore('int', f'{len(fx.conts)}', fx.sel)
        fx.conts.append(self.label())
        self.br(fx.entry)
    if fx.entry != "":
        # the finally block, once: the exception being handled is the one in flight on the way
        # out of an exception (a bare raise raises it: pys_reraise), else the one before the
        # statement, which a break or return in it restores; then each way out goes on
        self.place(fx.entry)
        self.exits.append(Exit("handler", old, outer))
        self.excs.append(Val("", "exc"))
        self.branch += 1
        self.narrowed = dict(fst)  # (each way in: fst holds on all of them)
        self.stmts(fin)
        self.branch -= 1
        self.excs.pop()
        self.exits.pop()
        disp = self.label()
        self.place(disp)
        ksel = self.mload('int', fx.sel)
        for j in range(len(fx.conts) - 1):
            nx = self.label()
            self.cbr(self.num_cmp('==', Val(ksel, "int"), Val(str(j), "int")).v, fx.conts[j], nx)
            self.place(nx)
        self.br(fx.conts[-1])
        if live:
            self.place(fx.conts[-1])
    elif live:
        self.place(done)
        self.narrowed = meet(ends)
        self.stmts(fin)
    if not live:
        self.narrowed = {}  # (no code follows)

def gen_assert_fails(self, n: Node) -> None:
    # the AssertionError of assert statement n, whose test is false: with its message
    v = self.expr(n.kids[1], "") if len(n.kids) > 1 else Val(self.sconst(""), "str")
    if self.eh and v.t != "str":
        self.throw(self.exc_value("AssertionError", [v]))  # (repr(e) shows the repr of v)
    else:
        self.raise_("AssertionError", self.to_str(v).v)

def gen_unnarrowed(self, bodies: list[list[Node]]) -> dict[str, str]:
    # a copy of narrowed without the names that the code of bodies binds or deletes: what
    # holds wherever an exception may come from in them
    out: dict[str, str] = {}
    if len(self.narrowed) > 0:
        names: dict[str, bool] = {}
        for b in bodies:
            collect(b, names)
            deleted(b, names)
        for nm in self.narrowed:
            if nm not in names:
                out[nm] = self.narrowed[nm]
    return out

def gen_clause_or(self, t: Node) -> Node:
    # except A or B: the class that the clause's expression gives where each operand names an
    # exception class (a class is true: A for or, B for and), as CPython evaluates it
    todo = [t]
    while len(todo) > 0:
        c = todo.pop()
        if c.kind == "boolop":
            todo += c.kids
        elif not self.exc_classes(c):
            return t
    while t.kind == "boolop":
        t = t.kids[0] if t.s == "or" else t.kids[1]
    return t

def gen_catches(self, h: Node) -> str:
    # the classes except clause h catches: "" for every one (a bare except, BaseException), else
    # "\1A\1B\1" (pys_exc_in): the exception classes, builtin or the program's, deriving
    # from those it names (a class of the program by its qualified name, its ExcClass's)
    self.line = h.line
    return self.catch_set(h.kids[0])

def gen_exc_classes(self, t: Node) -> bool:
    # does t, isinstance's second argument, name exception classes only (a name, or a tuple of names)
    for c in t.kids if t.kind == "tuple" else [t]:
        if c.kind != "name" or self.bound(c.s) and not (c.s in self.classes and self.classes[c.s].exc != ""):
            return False
        if not is_excname(c.s) and c.s not in self.classes:
            return False
    return True

def gen_exc_isinst(self, v: Val, t: Node) -> Val:
    # isinstance(v, t) of an exception (or an exception object, which may be None), t naming
    # exception classes: decided by v's class where its type decides it, else by its ExcClass
    names = t.kids if t.kind == "tuple" else [t]
    if v.t != "exc":
        yes = False
        maybe = False
        for c in names:
            yes = yes or self.derives(v.t, c.s)
            maybe = maybe or self.derives(c.s, v.t)
        if yes or not maybe:
            return Val(self.ptr_cmp('!=', v, Val('null', 'None')).v if yes and v.v not in self.nn else "true" if yes else "false", "bool")
    sets = self.catch_set(t)
    if v.t == "exc":
        return Val("true" if sets == "" else self.exc_match(v, sets), "bool")
    e0 = self.cur
    l1 = self.label()
    l2 = self.label()
    self.cbr(self.isnull(v), l2, l1)
    self.place(l1)
    r = self.exc_match(Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc"), sets)
    e1 = self.cur
    self.br(l2)
    self.place(l2)
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "false", e0)
    self.incoming(ph, r, e1)
    return Val(self.phi(ph), "bool")

def gen_catch_set(self, t: Node) -> str:
    # the classes that t, the classes an except clause names, catches (catches)
    names: list[str] = []
    for c in t.kids if t.kind == "tuple" else [t] if t.kind != "omit" else t.kids:
        if c.kind == "attr" and (self.dotted(c) == "builtins." + c.s or self.dotted(c) == "os.error"):
            c = mk("name", "OSError" if c.s == "error" else c.s, c.line, [])  # (builtins.ValueError, os.error)
        if self.dotted(c) == FROZENERR or (c.kind == "name" and c.s not in self.ltype and c.s not in self.gtypes and self.imported(c.s) == FROZENERR):
            c = mk("name", FROZENERR, c.line, [])
        if c.kind != "name" or c.s in self.ltype or c.s in self.gtypes or c.s in self.funcs or c.s in self.assigned:
            self.err("an except clause needs exception classes: a name, or a tuple of names")
        if c.s in self.unsupported:
            self.err(self.unsupported[c.s])
        if c.s in self.taliases:
            self.err(f"type alias '{short(c.s)}' cannot be used as a value (only annotations may name it)")
        if c.s in self.classes and self.classes[c.s].exc == "":
            self.err("catching classes that do not inherit from BaseException is not allowed")
        if c.s in self.classes and self.classes[c.s].hook != "":
            # (an imported module's class with a hook Pystachy never calls: an error where the program
            # uses it, catching it too; one bad otherwise, by its fields, may still be caught)
            self.err(self.classes[c.s].hook)
        if c.s in self.classes:
            names.append(c.s)
            continue
        x = "OSError" if c.s == "IOError" or c.s == "EnvironmentError" else c.s
        if x not in EXCBASES:
            self.err(f"name '{short(c.s)}' is not defined" if c.s not in PYBUILTINS else "catching classes that do not inherit from BaseException is not allowed")
        names.append(x)
    if t.kind == "tuple" and len(names) == 0:
        return "\x01\x01"  # (an empty tuple catches nothing)
    if len(names) == 0 or "BaseException" in names:
        return ""
    out: list[str] = []
    for k in EXCBASES:
        if k == FROZENERR and not self.hasfrozen:
            continue  # (no object of the program can raise it)
        for b in names:
            if b in EXCBASES and exc_derives(k, b):
                out.append(k)
                break
    for k in self.classes:
        for b in names:
            if self.classes[k].exc != "" and self.derives(k, b):
                out.append(k)
                break
    return "\x01" + "\x01".join(out) + "\x01"

def gen_as_type(self, h: Node) -> str:
    # the type of the name except clause h binds: the nearest exception class of the program
    # that every class it names derives from (the name is the exception's object), else exc
    t = h.kids[0]
    cs = t.kids if t.kind == "tuple" else [t]
    c = cs[0].s if t.kind != "omit" and len(cs) > 0 else ""
    while c in self.classes:
        ok = True
        for x in cs:
            ok = ok and self.derives(x.s, c)
        if ok:
            return c
        c = self.classes[c].base
    return "exc"

def gen_bind_as(self, name: str, e: Val, t: str) -> None:
    # except ... as name: name is exception e, or its object (of class t of the program). Where
    # name has another type, or no type yet but another binding in its scope (which may give it
    # one), it gets a variable of its own for the clause (the end of which unbinds both, see
    # unbind, as CPython deletes the name). Not a module's global that a function reads, which
    # would not see the exception
    v = e if t == "exc" else Val(self.rt("pys_exc_obj", "ptr", [f"ptr {e.v}"]), t)
    self.nn[v.v] = True
    had = self.ltype[name] if name in self.ltype else self.gtypes[name] if self.is_global(name) and name in self.gtypes else ""
    node = self.curfn.node
    if (had != "" and had != t) or (had == "" and binds_other(node.kids if node.kind == "block" else node.kids[2].kids, name)):
        f = self.global_reader(name) if self.modlevel else ""
        if f != "":
            self.err(f"except ... as {short(name)} is not supported here: the module's global '{short(name)}' has another type, so the clause binds a variable of its own, which {f}() would not see (use another name)")
        self.shadows.append([name, self.ltype.get(name, ""), self.lreg.get(name, ""), self.lflag.get(name, "")])
        if name in self.lflag:
            del self.lflag[name]
        self.alloca(t, name)
    self.store_name(name, v)

def gen_global_reader(self, name: str) -> str:
    # a function or method of the program that reads module global name, or ""
    fs = list(self.funcs.values())
    for ci in self.classes.values():
        fs += list(ci.methods.values())
    for f in fs:
        if f.mod != owner(name) or f.node.kind != "def" or name in f.params:
            continue
        if f.pending and name == f.orig.kids[0].kids[0].s:
            continue  # its shared body still spells the implicit class binding as cls
        body = f.node.kids[2].kids
        decl: dict[str, bool] = {}
        globals_in(body, decl)
        if name in decl or not (binds_other(body, name) or binds_as(body, name)):
            for st in body:
                if reads(st, name):
                    return short(f.name)
    return ""

def gen_unbinds(self, name: str) -> bool:
    # does unbind(name) clear an "is assigned" flag (a read that may follow tests it)
    if name in self.ltype and name in self.lflag or name not in self.ltype and name in self.gflag:
        return True
    for s in self.shadows:
        if s[0] == name and (s[3] != "" or (s[1] == "" and name in self.gflag)):
            return True
    return False

def gen_unshadow(self) -> None:
    # the end of the except clause whose name has a variable of its own (bind_as): the name is the other again
    s = self.shadows.pop()
    if s[1] == "":
        del self.ltype[s[0]]
        del self.lreg[s[0]]
    else:
        self.ltype[s[0]] = s[1]
        self.lreg[s[0]] = s[2]
    if s[3] != "":
        self.lflag[s[0]] = s[3]
    elif s[0] in self.lflag:
        del self.lflag[s[0]]

def gen_landing(self, l: str, slot: str, mark: Val) -> Val:
    # landing block l of a try statement, where an exception comes through the unwinder: its
    # landing op stores the exception in slot, as a raise in this function that goes there does
    # (see eh_ir), and both go on to the code after it, which takes the exception up: the
    # unwind actions since the try's mark run, and it becomes the exception being handled
    j = self.label()
    self.place(l)
    i = Ins("landing", "exc", "")
    i.a = [Val(slot, "%addr")]
    i.b = [j]
    self.put(i, 2)
    self.term = True
    self.place(j)
    x = self.mload('%ptr', slot)
    if self.fn.gbase != "":
        # (a generator's marks are relative to the depth of the unwind actions where it was
        # last resumed, which its consumer may have changed since: gen_enter)
        mark = Val(self.scalar('add', [mark, Val(self.mload('int', self.fn.gbase), 'int')]), "int")
    return Val(self.rt("pys_exc_begin", "ptr", [f"ptr {x}", f"i64 {mark.v}"]), "exc")

def gen_exc_match(self, e: Val, names: str) -> str:
    # does exception e belong to the classes names ("\1A\1B\1")
    i = Ins("exc.match", "bool", "")
    i.a = [e, Val(self.sconst(names), "str")]
    self.runtime("pys_exc_in")
    self.put(i, 2)
    return f"%t{i.r[1]}"

def gen_unbind(self, name: str) -> None:
    # the end of except ... as name: name is unbound, as after del name (but nothing is read),
    # and so are the variables of that name around it (bind_as)
    if name in self.ltype and name in self.lflag:
        self.mstore('bool', 'false', self.lflag[name])
    elif name != "" and name not in self.ltype and name in self.gflag:
        self.mstore('bool', 'false', f'@g.{name}.def')
    for s in self.shadows:
        if s[0] == name and s[3] != "":
            self.mstore('bool', 'false', s[3])
        elif s[0] == name and s[1] == "" and name in self.gflag:
            self.mstore('bool', 'false', f'@g.{name}.def')

def gen_exc_args(self, e: Node) -> list[Node]:
    # the arguments of raise E / raise E(args), checking that E is a builtin exception
    if e.kind == "call" and e.kids[0].kind == "name":
        name = e.kids[0].s
        args = e.kids[1:]
    elif e.kind == "name":
        name = e.s
        args = []
    else:
        self.err("raise needs an exception class or a call of one, such as raise ValueError(msg)")
    if name in self.ltype or name in self.gtypes or name in self.funcs:
        self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
    if name not in EXCEPTIONS:
        self.err(f"name '{name}' is not defined")
    if EXCEPTIONS[name] == "-":
        self.err(f"raising {name} is not supported")
    self.exc_kw(name, args, name + "()")
    npos = 0
    for a in args:
        npos += 1 if a.kind != "kw" else 0
    if EXCEPTIONS[name] == "u" and (npos != 5 or len([a for a in args if a.kind == "starred"]) > 0):
        self.err(f"function takes exactly 5 arguments ({npos} given)")  # (CPython's TypeError)
    oe = exc_base_of(name, "OSError")
    if npos > 1 and EXCEPTIONS[name] != "" and EXCEPTIONS[name] != "u" and not (oe and npos <= 3):
        self.err(f"{name}() with more than {'three arguments' if oe else 'one argument'} is not supported")
    return args

def gen_exc_kw(self, c: str, args: list[Node], what: str) -> None:
    # the keyword arguments of a call of builtin exception class c (or of its __init__, what):
    # those CPython's takes (an ImportError's name and path, ...), which set attributes that
    # only CPython reads (exc_vals evaluates and drops them)
    ok = (EXCKW["ImportError"] if exc_base_of(c, "ImportError") else EXCKW["AttributeError"] if exc_base_of(c, "AttributeError")
          else EXCKW["NameError"] if exc_base_of(c, "NameError") else "").split()
    for a in args:
        if a.kind == "kw" and len(ok) == 0:
            self.err(f"{what} takes no keyword arguments")
        if a.kind == "kw" and a.s not in ok:
            self.err(f"{what} got an unexpected keyword argument '{a.s}'")

def gen_exc_vals(self, args: list[Node], name: str = "") -> list[Val]:
    # the positional arguments of a call of builtin exception class name, its keyword arguments
    # evaluated in order too (exc_kw)
    vals: list[Val] = []
    for a in args:
        if a.kind == "kw":
            self.expr(a.kids[0], "")
        elif a.kind == "starred" and (a.kids[0].kind == "list" or a.kids[0].kind == "tuple") and len([x for x in a.kids[0].kids if x.kind == "starred"]) == 0:
            for x in a.kids[0].kids:
                vals.append(self.expr(x, ""))  # (*[a, b] of a display: its items)
        elif a.kind == "starred":
            v = self.unwrap(self.expr(a.kids[0], ""), f"TypeError: {name + '() argument' if name != '' else 'Value'} after * must be an iterable, not NoneType")
            if not is_tuple(v.t):
                self.err(f"unpacking a {typestr(v.t)} into the arguments of an exception is not supported (a tuple's items are)")
            for i in range(len(targs(v.t))):
                vals.append(self.tget(v, i))
        else:
            vals.append(self.expr(a, ""))
    return vals

def gen_exc_class(self, e: Node) -> str:
    # the class that e, the exception of a raise statement, names or calls: a builtin exception
    # class (EXCEPTIONS) or a class of the program; "" for any other expression (a variable,
    # a call of a function), whose value is the exception
    c = e.kids[0] if e.kind == "call" else e
    if c.kind != "name" or c.s in self.funcs or c.s in self.ltype or c.s in self.gtypes or self.unbound_local(c.s):
        return ""  # (a local the function assigns further on: reading it is the error, see read_ahead)
    return c.s if c.s in self.classes or c.s in EXCEPTIONS else ""

def gen_cause_value(self, c: Node) -> Val:
    # raise ... from c: c's value, which CPython evaluates before it calls the raised class (a
    # class of the program named is only looked up, Val("", k): cause() calls it, after the raised
    # class; a builtin class's exception is made here, which no code of the program sees)
    if c.kind == "None":
        return Val("", "")
    k = self.exc_class(c)
    if k == "" or k in self.classes:
        return self.exc_value_of(c, k, False)
    name = c.kids[0].s if c.kind == "call" else c.s
    vals = self.exc_vals(self.exc_args(c), c.kids[0].s if c.kind == "call" else "")
    if not self.causeread or not self.eh or name == "SystemExit":
        return Val("", "")
    return self.exc_value("OSError" if name == "IOError" or name == "EnvironmentError" else name, vals)

def gen_cause(self, c: Node, v: Val) -> Val:
    # raise ... from c, of c's value v (cause_value), after the raised class is called: checked (an
    # exception class, a call of one, an exception or None: else CPython's TypeError is raised
    # instead), and a class called; the exception it makes, the raised exception's __cause__, is
    # returned where the program reads that (Gen.causeread), else only a traceback would show it
    # (Val("", ""): none)
    if c.kind == "None":
        return Val("", "")
    k = self.exc_class(c)
    if k == "" or k in self.classes:
        if v.v == "" and k != "":
            v = self.exc_object(k, [])  # (a class of the program named: called now)
        if unopt(v.t) == "exctype" and is_opt(v.t):
            # (a class object that may be None: None is no cause, as from None; a class, an
            # object of it, as below)
            e0 = self.cur
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, l2, l1)
            self.place(l1)
            made = self.exc_call(Val(v.v, "exctype"), [], 16)
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "opt[exc]", "")
            self.incoming(ph, "null", e0)
            self.incoming(ph, made.v, e1)
            v = Val(self.phi(ph), "opt[exc]")
        elif unopt(v.t) == "exctype":
            v = self.exc_call(v, [], 16)  # (from C of a class object C: an object of its class, C())
        if v.t != "exc" and v.t != "opt[exc]" and v.t != "None" and not (v.t in self.classes and self.classes[v.t].exc != ""):
            self.raise_("TypeError", self.sconst("exception causes must derive from BaseException"))
            self.place(self.label())  # (what follows, the raise itself, is never reached)
            return Val("", "")
        if self.causeread and v.t in self.classes:
            return self.exc_of(v)
        return v if self.causeread and (v.t == "exc" or v.t == "opt[exc]") else Val("", "")  # (an exception, or None: no cause)
    return v  # (a builtin class's exception, which cause_value made)

def gen_exc_value_of(self, e: Node, k: str, make: bool = True) -> Val:
    # the value of e, the exception of a raise statement, unless it is a builtin exception class
    # or a call of one: a class of the program k (or a call of it) makes an object of it, a class
    # named only where make (else it is looked up, Val("", k), and the raise calls it later)
    if k == "":
        return self.expr(e, "")
    if self.classes[k].exc == "":
        self.err(f"'{short(k)}' is not an exception class: exceptions must derive from BaseException")
    self.class_ready(e.kids[0] if e.kind == "call" else e)  # (looked up first, as a call of it does)
    if not make and e.kind != "call":
        return Val("", k)
    return self.exc_object(k, e.kids[1:] if e.kind == "call" else [])

def gen_raise_stmt(self, n: Node) -> None:
    # raise E(args) [from C]: CPython's last traceback line, "E: str(arg)" (KeyError: repr(arg);
    # several arguments: their tuple's repr); SystemExit ends the program like sys.exit. In a
    # program that has try or with, it throws the exception CPython makes (exc_value), which the
    # program ends with as before if nothing catches it
    if len(n.kids) == 0:
        # a bare raise: the exception the except clause around it handles, or else the one
        # being handled where it runs (in a function an except clause calls)
        if len(self.excs) > 0 and self.excs[-1].v != "":
            self.throw(self.excs[-1])
        elif self.eh:
            self.rt("pys_reraise", "void", [])
            self.unreachable()
        else:
            self.raise_("RuntimeError", self.sconst("No active exception to reraise"))
        return
    e = n.kids[0]
    k = self.exc_class(e)
    if self.curfn.gen and not self.eh and k != "" and (exc_derives(k, "StopIteration") if k not in self.classes else self.derives(k, "StopIteration")):
        # (PEP 479: a StopIteration that leaves a generator is a RuntimeError; with exceptions
        # off, nothing in the generator can catch it first)
        if k in self.classes:
            self.exc_value_of(e, k)
        else:
            self.exc_vals(self.exc_args(e), k)
        self.raise_("RuntimeError", self.sconst("generator raised StopIteration"))
        return
    if k == "" or k in self.classes:
        # e's value and then the cause's, and only then are their classes called and checked, as
        # CPython's raise does: raise E from f() calls f() before E
        v = self.exc_value_of(e, k, len(n.kids) < 2)
        cv = self.cause_value(n.kids[1]) if len(n.kids) > 1 else Val("", "")
        if v.v == "" and k != "":
            v = self.exc_object(k, [])  # (a class of the program named)
        if unopt(v.t) == "exctype":
            # raise C of a class object C: an object of its class, C()
            if is_opt(v.t):
                self.guard(self.ptr_cmp('==', v, Val('null', 'None')).v, "TypeError: exceptions must derive from BaseException")
                v = Val(v.v, "exctype")
            v = self.exc_call(v, [], 8)
        if v.t in self.classes and self.classes[v.t].exc != "":
            v = self.exc_of(v)
        if v.t == "opt[exc]":
            # (an exception or None, as __exit__ takes it: raise None is CPython's TypeError)
            self.guard(self.ptr_cmp('==', v, Val('null', 'None')).v, "TypeError: exceptions must derive from BaseException")
            v = Val(v.v, "exc")
        if v.t != "exc":
            self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
        if len(n.kids) > 1:
            cv = self.cause(n.kids[1], cv)
            if cv.v != "":
                self.rt("pys_exc_setcause", "void", [f"ptr {v.v}", f"ptr {cv.v}"])
        self.throw(v)
        return
    name = e.kids[0].s if e.kind == "call" else e.s
    vals = self.exc_vals(self.exc_args(e), name)
    cause = Val("", "")
    if len(n.kids) > 1:
        cause = self.cause(n.kids[1], self.cause_value(n.kids[1]))
    if n.s == "init":
        # a module's raise of ImportError at its top level (Loader.init_raise()): under an optional
        # import (a "guard" in a uimport) the module returns, not imported, so that the importer's
        # handler runs and a later import runs its code again
        g = self.curfn.ll + ".guard"
        self.global_var(g, "bool")
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.mload('bool', g), l1, l2)
        self.place(l1)
        self.mstore('bool', 'false', f'{self.curfn.ll}.done')
        self.ret_(Val("null", "None"))
        self.place(l2)
    if name == "SystemExit":
        self.exit_(vals, False)
        return
    if self.eh:
        xv = self.exc_value("OSError" if name == "IOError" or name == "EnvironmentError" else name, vals)
        if cause.v != "":
            self.rt("pys_exc_setcause", "void", [f"ptr {xv.v}", f"ptr {cause.v}"])
        self.throw(xv)
        return
    if name == "SyntaxError" or name == "IndentationError" or name == "TabError":
        # CPython's traceback takes str(e), which is str(msg), then prints "E: " and str(msg or
        # "<no detail available>"), the ": " even before an empty str(msg), which pys_raise leaves
        # out: the raise op's kind operand is then that whole line, and its message empty
        if len(vals) == 1:
            self.to_str(vals[0])
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.truth(vals[0]), l1, l2)
            self.place(l1)
            line = self.rt("pys_str_add", "ptr", [f"ptr {self.sconst(name + ': ')}", f"ptr {self.to_str(vals[0]).v}"])
            self.raise_(name, self.sconst(""), line)
            self.place(l2)
        self.raise_(name, self.sconst("<no detail available>"))
        return
    name = "OSError" if name == "IOError" or name == "EnvironmentError" else name
    if len(vals) > 1 and exc_base_of(name, "OSError"):
        oe = self.os_error(name, vals)
        self.raise_(name, oe[1], oe[0])
        return
    if EXCEPTIONS[name] == "u":
        self.raise_(name, self.unicode_error(name, vals)[0])
        return
    if len(vals) > 1:
        msg = self.repr(self.tuple_(vals)).v
    elif len(vals) == 1:
        msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
    else:
        msg = self.sconst("")
    self.raise_(name, msg)

def gen_os_error(self, name: str, vals: list[Val]) -> list[str]:
    # OSError(errno, strerror[, filename]) of builtin class name, as CPython's makes it: str(e)
    # "[Errno n] strerror" (then ": " and repr(filename), unless it is None), args (errno,
    # strerror) (and None), of the subclass the errno names where name is OSError itself.
    # Gives its kind, str(e) and what repr(e) shows between its parentheses
    no = vals[0]
    kind = self.sconst(name) if name in EXCBASES else ""  # (an exception class of the program's is its own)
    if name == "OSError" and (no.t == "int" or no.t == "bool" or no.t == BIG):
        kind = self.rt("pys_exc_errcls", "ptr", [f"i64 {self.big_status(no).v}"])  # (past 64 bits, no errno's: bigints.py)
    elif name == "OSError" and is_sopt(no.t) and (unopt(no.t) == "int" or unopt(no.t) == "bool" or no.t == BIGOPT):
        # (an errno that may be None: OSError itself if it is)
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.isnull(no), l1, l2)
        self.place(l1)
        self.br(l3)
        self.place(l2)
        k = self.rt("pys_exc_errcls", "ptr", [f"i64 {self.big_status(self.deref(no)).v}"])
        b2 = self.cur
        self.br(l3)
        self.place(l3)
        ph = Ins("phi", "str", "")
        self.incoming(ph, kind, l1)
        self.incoming(ph, k, b2)
        kind = self.phi(ph)
    msg = self.cat(Val(self.sconst("[Errno "), "str"), self.to_str(no))
    msg = self.cat(self.cat(msg, Val(self.sconst("] "), "str")), self.to_str(vals[1]))
    args = self.cat(self.cat(self.repr(no), Val(self.sconst(", "), "str")), self.repr(vals[1]))
    if len(vals) == 3 and vals[2].t == "None":
        args = self.cat(args, Val(self.sconst(", None"), "str"))
    elif len(vals) == 3 and is_opt(vals[2].t):
        # (a filename that may be None: in args if it is, else in str(e))
        nn = self.isnull(vals[2])
        na = self.cat(args, Val(self.sconst(", None"), "str"))
        fm = self.cat(self.cat(msg, Val(self.sconst(": "), "str")), self.repr(vals[2]))
        args = Val(self.select(nn, na, args), "str")
        msg = Val(self.select(nn, msg, fm), "str")
    elif len(vals) == 3:
        msg = self.cat(self.cat(msg, Val(self.sconst(": "), "str")), self.repr(vals[2]))
    return [kind, msg.v, args.v]

def gen_unicode_error(self, name: str, vals: list[Val]) -> list[str]:
    # UnicodeDecodeError(encoding, object, start, end, reason) or UnicodeEncodeError(...) of the
    # types CPython's constructor takes (a bytes object, or a str): str(e), which names the byte or
    # character at start, or the range to end, as CPython's does, and what repr(e) shows between
    # its parentheses
    dec = name == "UnicodeDecodeError"
    want = ["str", "bytes" if dec else "str", "int", "int", "str"]
    for i in range(5):
        # (CPython's TypeErrors)
        if ("int" if vals[i].t == "bool" or vals[i].t == BIG else vals[i].t) == want[i]:
            continue
        if i == 1 and dec:
            self.err(f"a bytes-like object is required, not '{tname(vals[i].t)}'")
        if i == 2 or i == 3:
            self.err(f"'{tname(vals[i].t)}' object cannot be interpreted as an integer")
        self.err(f"argument {i + 1} must be {want[i]}, not {tname(vals[i].t)}")
    bounds: list[Val] = []
    for i in [2, 3]:
        v = vals[i]
        if v.t == BIG:
            self.guard(self.scalar("xor", [Val(self.big_fits([v]), "bool"), Val("true", "bool")]),
                       "OverflowError: Python int too large to convert to C ssize_t")
            bounds.append(self.big_lo(v))
        else:
            bounds.append(self.as_int(v))
    msg = self.rt("pys_unicode_error_str", "ptr", [f"i64 {1 if dec else 0}", f"ptr {vals[0].v}", f"ptr {vals[1].v}",
                                                   f"i64 {bounds[0].v}", f"i64 {bounds[1].v}", f"ptr {vals[4].v}"])
    args = self.rt("pys_str_slice", "ptr", [f"ptr {self.repr(self.tuple_(vals)).v}", "i64 1", "i64 -1"])
    return [msg, args]

def gen_exc_str_args(self, msg: str) -> str:
    # what repr(e) shows between its parentheses for one str argument, msg: null, the repr of
    # str(e), but for an empty str '', which repr(ValueError("")) shows and an exception without
    # arguments (an empty str(e) too, and null) does not: decided where msg is a constant
    if msg.startswith("@s."):
        return self.sconst("''") if self.strvals[int(msg[3:])] == "" else "null"
    empty = self.num_cmp('==', Val(self.mload('int', msg), "int"), Val("0", "int"))  # (its length in bytes)
    return self.select(empty.v, Val(self.sconst("''"), "%ptr"), Val("null", "%ptr"))

def gen_exc_value(self, name: str, vals: list[Val]) -> Val:
    # the exception name(*vals) of a builtin class name (pys_exc_new): str(e), and what repr(e)
    # shows between its parentheses (null: the repr of str(e), as for one str argument)
    args = "null"
    detail = ""
    if name == "SyntaxError" or name == "IndentationError" or name == "TabError":
        # str(e) is str(msg) ("None" without), but its traceback shows "E: " and str(msg or
        # "<no detail available>")
        msg = self.to_str(vals[0]).v if len(vals) == 1 else self.sconst("None")
        no = Val(self.sconst("<no detail available>"), "str")
        detail = self.select(self.truth(vals[0]), Val(msg, "str"), no) if len(vals) == 1 else no.v
        if len(vals) == 0:
            args = self.sconst("")
        elif vals[0].t != "str":
            args = self.repr(vals[0]).v
        else:
            args = self.exc_str_args(msg)
    elif len(vals) > 1 and exc_base_of(name, "OSError"):
        oe = self.os_error(name, vals)
        return Val(self.rt("pys_exc_new", "ptr", [f"ptr {oe[0]}", f"ptr {oe[1]}", f"ptr {oe[2]}"]), "exc")
    elif EXCEPTIONS.get(name, "") == "u":
        ue = self.unicode_error(name, vals)
        return Val(self.rt("pys_exc_new", "ptr", [f"ptr {self.sconst(name)}", f"ptr {ue[0]}", f"ptr {ue[1]}"]), "exc")
    elif len(vals) > 1:
        msg = self.repr(self.tuple_(vals)).v
        args = self.rt("pys_str_slice", "ptr", [f"ptr {msg}", "i64 1", "i64 -1"])
    elif len(vals) == 1:
        msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
        if vals[0].t != "str" and name != "KeyError":
            args = self.repr(vals[0]).v  # (a KeyError's message is its argument's repr already)
        elif name != "KeyError":
            args = self.exc_str_args(msg)
    else:
        msg = self.sconst("")
    e = self.rt("pys_exc_new", "ptr", [f"ptr {self.sconst(name)}", f"ptr {msg}", f"ptr {args}"])
    if detail != "":
        e = self.rt("pys_exc_detail", "ptr", [f"ptr {e}", f"ptr {detail}"])
    return Val(e, "exc")

def gen_exit_(self, vals: list[Val], sysx: bool) -> None:
    # sys.exit(code) (sysx) and raise SystemExit(code): None is status 0, an int is the status,
    # and anything else is printed to stderr with status 1. In a program that has try or with, a code
    # whose str() or repr() the runtime would not show as CPython's (None, a bool, several
    # arguments, anything but an int or a str) is thrown as the exception exit_value makes; a
    # value that may be None (an object, or T | None) is tested first, and then is its T
    opt = len(vals) == 1 and (vals[0].t in self.classes or is_opt(vals[0].t))
    if self.eh and not opt and (len(vals) != 1 or (vals[0].t != "int" and vals[0].t != "str")):
        self.throw(self.exit_value(vals))
        return
    if len(vals) > 1:
        self.rt("pys_exit_msg", "void", [f"ptr {self.repr(self.tuple_(vals)).v}"])
    elif len(vals) == 0 or vals[0].t == "None":
        self.rt("pys_exit", "void", ["i64 0"])
    elif vals[0].t == "int" or vals[0].t == "bool" or vals[0].t == BIG:
        self.rt("pys_exit", "void", [f"i64 {self.big_status(vals[0]).v}"])  # (a promoting int's: bigints.py)
    else:
        if vals[0].t in self.classes or is_opt(vals[0].t):
            # an object that is None at run time is status 0 too
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.isnull(vals[0]), l1, l2)
            self.place(l1)
            if self.eh:
                # (sys.exit(None) is SystemExit(), but SystemExit(None) keeps its None, see exit_value)
                self.throw(self.no_code() if sysx else self.exit_value([Val("null", "None")]))
            else:
                self.rt("pys_exit", "void", ["i64 0"])
                self.unreachable()
            self.place(l2)
        if is_sopt(vals[0].t) or (self.eh and is_opt(vals[0].t)):
            self.exit_([self.deref(vals[0])], sysx)  # (an int is the status)
            return
        if self.eh and vals[0].t != "str":
            self.throw(self.exc_value("SystemExit", vals))
            return
        self.rt("pys_exit_msg", "void", [f"ptr {self.to_str(vals[0]).v}"])
    self.unreachable()

def gen_no_code(self) -> Val:
    # SystemExit(None): status 0, str(e) ""
    e = self.sconst("")
    return Val(self.rt("pys_exc_exit", "ptr", ["i64 0", f"ptr {e}", f"ptr {e}"]), "exc")

def gen_exit_value(self, vals: list[Val]) -> Val:
    # SystemExit(*vals): an int or bool code is the status the program ends with if nothing
    # catches it, None (or none) status 0; anything else is shown, with status 1. (sys.exit(None)
    # is SystemExit(), but SystemExit(None) shows its None: str(e) "None")
    if len(vals) == 0:
        return self.no_code()
    if len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool" or vals[0].t == "None" or vals[0].t == BIG):
        s = self.to_str(vals[0]).v
        return Val(self.rt("pys_exc_exit", "ptr", [f"i64 {self.big_status(vals[0]).v if vals[0].t != 'None' else '0'}", f"ptr {s}", f"ptr {s}"]), "exc")
    if len(vals) == 1 and is_opt(vals[0].t):
        # a value that may be None: SystemExit(None), or the exception of the value it holds
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.isnull(vals[0]), l1, l2)
        self.place(l1)
        e1 = self.exit_value([Val("null", "None")])
        b1 = self.cur
        self.br(l3)
        self.place(l2)
        e2 = self.exit_value([self.deref(vals[0])])
        b2 = self.cur
        self.br(l3)
        self.place(l3)
        ph = Ins("phi", "exc", "")
        self.incoming(ph, e1.v, b1)
        self.incoming(ph, e2.v, b2)
        return Val(self.phi(ph), "exc")
    return self.exc_value("SystemExit", vals)

def gen_exc_object(self, c: str, args: list[Node]) -> Val:
    # c(args), c an exception class: an object made as BaseException.__new__ makes it (its
    # ExcClass, and the args kept as str(e) and repr(e) show them, see exc_keep), with the
    # class-body defaults, then given to the __init__ of c or of the nearest base that has
    # one; without one, the class takes any positional arguments. All the arguments are
    # evaluated first, in order, as CPython evaluates them before it makes the object
    ci = self.classes[c]
    if ci.bad != "":
        self.err(ci.bad)
    line = self.line
    init = ci.methods["__init__"] if "__init__" in ci.methods else None
    vals: list[Val] = []
    kws: list[Node] = []
    if init is not None and len([a for a in args if a.kind == "kw" and not pure_arg(a.kids[0])]) > 0:
        # (a keyword argument that fits no parameter of __init__ is reported as call_fn reports
        # it, before the loop evaluates one with the type of its parameter)
        self.arity(init, 1, args)
    for a in args:
        if a.kind == "kw" and init is None:
            # (the keywords its builtin base's __init__ takes, ImportError's name and path, ...)
            self.exc_kw(ci.exc, [a], f"{short(c)}()")
            self.expr(a.kids[0], "")
        elif a.kind == "kw":
            # (its value is __init__'s, see vnode: E(xs, k=f(xs)) keeps xs as f left it, and a
            # k=f() that raises leaves no object made; a constant is evaluated where it goes)
            kws.append(a if pure_arg(a.kids[0]) else mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], self.kw_type(init, a.s)))]))
        else:
            j = len(vals) + 1
            vals.append(self.expr(a, init.ptypes[j] if init is not None and j < init.npos else ""))
    if init is not None and len(vals) >= init.npos:
        self.err(f"{short(init.cls)}.__init__() takes {init.npos} positional argument{'s' if init.npos > 1 else ''} but {len(vals) + 1} were given")
    o = self.alloc_fixed(c)
    self.nn[o.v] = True
    self.xcls[c] = True
    self.setfield(o, self.field(o, " cls"), " cls", Val(f"@x.{c}", "str"))
    # (with an __init__ of the program, an OSError's args are left empty, and a SystemExit's
    # code None, until its super().__init__() sets them, as OSError.__new__ and SystemExit.__init__ do)
    self.exc_keep(o, vals if init is None or not self.derives(c, "OSError") else vals[:0], init is None)
    self.class_defaults(o)
    self.line = line
    if init is not None:
        self.init_result(self.call_fn(init, [o] + vals, kws))
    return o

def gen_class_defaults(self, o: Val) -> None:
    # new object o's class-body defaults: CPython's class attributes, which o reads until it
    # assigns them, as it is made (exc_object, new_obj), so that a later call of its __init__
    # sees what o holds then. A class variable is read from the class (see getfield)
    ci = self.classes[o.t]
    for fl in ci.fields:
        if fl in ci.fdefault and o.t + "." + fl not in self.cvars:
            h = self.default_home(ci, fl)
            t = ci.ftypes[fl]
            identity = fl in ci.fbox and numeric_identity(t)
            if not is_const(ci.fdefault[fl]) or identity:
                self.class_default(h, fl)  # (compiled before the class statement runs)
            v = Val(self.mload(t, h.fglob[fl]), t) if fl in h.fglob else self.coerce(self.expr(ci.fdefault[fl], t), t)
            if identity:
                self.dyn_id_read(v, h.fglob[fl] + ".box")
            self.setfield(o, self.field(o, fl), fl, v)

def gen_exc_keep(self, o: Val, vals: list[Val], coded: bool = True) -> None:
    # what exception object o keeps of its args vals (BaseException.__new__, and its __init__
    # through super().__init__): str(e) (a KeyError's: the repr of its one argument) and the
    # text between repr(e)'s parentheses; a SystemExit's status and whether its code is one
    # (unless coded is False: its code is None)
    c = o.t
    if len(vals) > 3 and self.derives(c, "OSError"):
        self.err(f"{short(c)}() with more than three arguments is not supported")
    if len(vals) > 1 and self.derives(c, "OSError"):
        oe = self.os_error(c, vals)  # ("[Errno n] text")
        sv = oe[1]
        av = oe[2]
    elif len(vals) == 0:
        sv = self.sconst("")
        av = sv
    elif len(vals) == 1:
        av = self.repr(vals[0]).v
        sv = av if self.derives(c, "KeyError") else self.to_str(vals[0]).v
    else:
        sv = self.repr(self.tuple_(vals)).v
        av = self.rt("pys_str_slice", "ptr", [f"ptr {sv}", "i64 1", "i64 -1"])
    self.setfield(o, self.field(o, " str"), " str", Val(sv, "str"))
    self.setfield(o, self.field(o, " args"), " args", Val(av, "str"))
    if self.derives(c, "SystemExit"):
        code = "0"
        hc = "true" if len(vals) == 0 or not coded else "false"
        t = vals[0].t if len(vals) == 1 and coded else ""
        if t == "int" or t == "bool" or t == BIG:
            code = self.big_status(vals[0]).v  # (a promoting int's: bigints.py)
        if t != "":
            # (an int | None or a bool | None is a status, 0 if it is None; another value that
            # may be None is one only if it is None)
            st = t == "int" or t == "bool" or t == BIG or t == "None" or (is_sopt(t) and (unopt(t) == "int" or unopt(t) == "bool" or t == BIGOPT))
            hc = "true" if st else self.isnull(vals[0]) if t in self.classes or is_opt(t) else "false"
        self.setfield(o, self.field(o, " code"), " code", Val(code, "int"))
        self.setfield(o, self.field(o, " hc"), " hc", Val(hc, "bool"))
        if is_sopt(t) and (unopt(t) == "int" or unopt(t) == "bool" or t == BIGOPT):
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.isnull(vals[0]), l2, l1)
            self.place(l1)
            self.setfield(o, self.field(o, " code"), " code", self.big_status(self.deref(vals[0])))
            self.place(l2)

def gen_exc_of(self, v: Val) -> Val:
    # the exception that raises exception object v
    self.notnone(v, "TypeError: exceptions must derive from BaseException")
    return Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc")

def gen_exc_brepr(self, o: Val) -> Val:
    # BaseException.__repr__ of exception object o: the name of its class, and its args
    a = self.getfield(o, self.field(o, " args"), " args")
    return Val(self.rt("pys_exc_brepr", "ptr", [f"ptr {o.v}", f"ptr {a.v}"]), "str")

def gen_super_call(self, sc: Node, m: str, args: list[Node], based: bool = False, read: bool = False) -> Val:
    # super().m(args) in a method of an exception class (based: Base.m(self, args), for its
    # base): the base's method m, or what BaseException's __init__ (keep the args), __str__ and
    # __repr__ do
    cls = self.curfn.cls
    # the object super() binds: the method's first parameter, self (a static method's first
    # argument); none in a class method, whose super() binds cls, the class
    me0 = self.curfn.params[0] if cls != "" and len(self.curfn.params) > 0 and (based or len(sc.kids) > 1 or self.curfn.deco != "classmethod") else ""
    # (super(C, self), in a method of class C, is super(): C as the loader qualifies it, m$C in
    # module m, and read as the module's name, not a local's)
    same = len(sc.kids) == 3 and sc.kids[1].kind == "name" and sc.kids[1].s == cls and self.globread(cls) and sc.kids[2].kind == "name" and sc.kids[2].s == me0
    ordinary = cls in self.classes and self.classes[cls].tag > 0
    if ordinary and len(sc.kids) == 3 and sc.kids[1].kind == "name" and sc.kids[1].s in self.classes and self.derives(cls, sc.kids[1].s) and self.globread(sc.kids[1].s) and sc.kids[2].kind == "name" and sc.kids[2].s == me0:
        same = True
    if (len(sc.kids) > 1 and not same) or cls == "" or (self.classes[cls].exc == "" and not ordinary):
        self.err("super() is only supported without arguments in a method of a class with a supported base (super(C, self) in a method of C is super())")
    if me0 == "":
        self.err("super() in a class method (which binds cls, the class) or a static method without parameters is not supported")
    me = self.expr(mk("name", me0, sc.line, []), "")
    start = sc.kids[1].s if ordinary and len(sc.kids) == 3 else cls
    b = self.classes[start].base
    if b in self.classes and m in self.classes[b].methods:
        bm = self.classes[b].methods[m]
        if bm.prop:
            if based:
                self.err(f"{short(b)}.{m} is a property: read it on an instance")
            value = self.call_fn(bm, [me], [], direct=True)
            return value if read else self.obj_call(value, args, "")
        if read:
            self.err("reading super() attributes is only supported for properties")
        if bm.deco != "" and not based:
            # a static or class method of the base gets no object (Base.m(self, ...) passes
            # self as its first argument), and a class method's cls would be the object's class
            self.cls_bound(bm, cls, True)
            return self.call_fn(bm, [], args, direct=True)
        return self.call_fn(bm, [me], args, direct=True)
    if read:
        self.err(f"super() has no supported property '{m}' in the base of {short(cls)}")
    if ordinary:
        if m == "__init__" and b == "":
            if len(args) != 0:
                self.err("object.__init__() takes exactly one argument (the instance to initialize)")
            return Val("null", "None")
        self.err(f"super() has no supported method '{m}' in the base of {short(cls)}")
    if m == "__init__":
        self.exc_kw(b, args, f"{short(b)}.__init__()")
        vals = self.exc_vals(args)
        self.exc_keep(me, vals)
        return Val("null", "None")
    if (m == "__str__" or m == "__repr__") and len(args) == 0:
        return self.getfield(me, self.field(me, " str"), " str") if m == "__str__" else self.exc_brepr(me)
    self.err(f"super().{m}() is not supported: only __init__, __str__, __repr__ and the methods of a base class of the program")
    return me

def gen_exc_helpers(self, c: str) -> None:
    # the ExcClass of exception class c (runtime.c's exceptions): its name, which an except
    # clause matches, the name an uncaught exception's line shows, and its str, repr and (for
    # a SystemExit) exit functions: those of the class, or BaseException's
    ci = self.classes[c]
    line = ci.node.line
    me = mk("name", "self", line, [])
    noann = mk("noann", "", line, [])
    bodies: list[list[Node]] = []
    for m in ["__str__", "__repr__"]:
        if m in ci.methods:
            r = mk("call", "", line, [mk("attr", m, line, [me])])
        elif m == "__str__":
            r = mk("attr", " str", line, [me])
        else:
            r = mk("call", "", line, [mk("name", "__pys_exc_repr", line, []), me])
        bodies.append([mk("return", "", line, [r])])
    if self.derives(c, "SystemExit"):
        # the SystemExit that ends the program as this one does (exit_value)
        sysexit = mk("name", "SystemExit", line, [])
        code = mk("block", "", line, [mk("return", "", line, [mk("call", "", line, [sysexit, mk("attr", " code", line, [me])])])])
        bodies.append([mk("if", "", line, [mk("attr", " hc", line, [me]), code, mk("block", "", line, [])]),
                       mk("return", "", line, [mk("call", "", line, [sysexit, mk("attr", " str", line, [me])])])])
    names = ["str", "repr", "exit"]
    for i in range(len(bodies)):
        f = FnInfo(names[i], f"@x.{names[i]}.{c}", ci.node, c)
        f.params = ["self"]
        f.ptypes = [c]
        f.defaults = [noann]
        f.dglob = [""]
        f.ret = "exc" if i == 2 else "str"
        self.function(f, bodies[i])
    d = Data("exception", f"@x.{c}")
    d.refs = [self.sconst(c), self.sconst(self.exc_disp(c)), f"@x.str.{c}", f"@x.repr.{c}", f"@x.exit.{c}" if len(bodies) == 3 else "null"]
    d.text = "global" if c in self.xmods else ""  # (C.__module__ = v writes its displayed name: exc_set_module)
    self.consts.append(d)

def gen_exc_disp(self, c: str) -> str:
    # the name of exception class c that its uncaught exceptions show, and its __module__: its
    # module's and its own ("mods.errs.Missing", "Missing" in the main program), or those of a
    # __module__ = "name" in its own class body, which CPython's class takes from its namespace
    ci = self.classes[c]
    if "__module__" not in ci.fdefault or "__module__" not in self.body_names(ci.node) or ci.fdefault["__module__"].kind != "str":
        return shown(c)
    m = ci.fdefault["__module__"].s
    if m == "builtins":
        self.err(f"__module__ = 'builtins' in the body of class {short(c)} is not supported")
    return short(c) if m == "__main__" else m + "." + short(c)

def gen_exc_set_module(self, cn: Node, v: Val) -> None:
    # C.__module__ = v of exception class C of the program: its ExcClass's displayed name becomes
    # v's and C's (runtime.c's pys_exc_setmodule), which an uncaught exception's line, C.__module__
    # and type(e).__module__ show from then on, as CPython's traceback shows the class's __module__;
    # so does the class variable of a __module__ in its body, which its objects read
    c = cn.s
    self.class_ready(cn)
    if v.t != "str":
        self.err(f"assigning {typestr(v.t)} to {short(c)}.__module__ is not supported: assign a str")
    self.xcls[c] = True
    self.rt("pys_exc_setmodule", "void", [f"ptr @x.{c}", f"ptr {v.v}"])
    if c + ".__module__" in self.cvars:
        self.class_store(self.cvar(cn, "__module__"), "__module__", v)

def gen_throw(self, e: Val) -> None:
    # raise exception e: to the landing block around, or out of the function (pys_throw)
    i = Ins("throw", "", "")
    i.a = [e]
    self.runtime("pys_throw")
    self.add(i)
    self.term = True

def gen_raise_(self, name: str, msg: str, kind: str = "") -> None:
    # raise exception name: the error line is "<kind>: <msg>", where kind is name unless given
    i = Ins("raise", "", name)
    i.a = [Val(kind if kind != "" else self.sconst(name), "str"), Val(msg, "str")]
    self.runtime("pys_raise")
    self.add(i)
    self.term = True

def gen_exc_class_value(self, c: str) -> Val:
    # exception class c as a value: its class object (runtime.c's exceptions), a builtin class's
    # (OSError's other names are OSError) or one of the program's, whose ExcClass it holds and
    # whose objects a call of a class object makes (exc_call: the program's classes used as
    # values, xvals)
    if c in self.classes:
        if self.classes[c].hook != "":
            self.err(self.classes[c].hook)
        self.xcls[c] = True
        self.xvals[c] = True
        r = self.rt("pys_exc_proto", "ptr", [f"ptr {self.sconst(c)}", f"ptr @x.{c}"])
    else:
        k = "OSError" if c == "IOError" or c == "EnvironmentError" else c
        r = self.rt("pys_exc_proto", "ptr", [f"ptr {self.sconst(k)}", "ptr null"])
    self.nn[r] = True
    return Val(r, "exctype")

def gen_exc_type_of(self, v: Val) -> Val:
    # type(v) of an exception, or of an object of an exception class of the program, which may be
    # None (an exception too, opt[exc]): NoneType then, a class object of that name too (no
    # exception class's). A call of the class object may make an object of v's class (exc_ctors:
    # the classes deriving from v's)
    self.xtypes[unopt(v.t)] = True
    if v.t == "exc" or v.v in self.nn:
        r = self.rt("pys_exc_canon", "ptr", [f"ptr {v.v if v.t == 'exc' or v.t == 'opt[exc]' else self.exc_of(v).v}"])
        self.nn[r] = True
        return Val(r, "exctype")
    e0 = self.cur
    l1 = self.label()
    l2 = self.label()
    nt = self.exc_none_class().v
    self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, l2, l1)
    self.place(l1)
    r = self.rt("pys_exc_canon", "ptr", [f"ptr {v.v if v.t == 'opt[exc]' else self.rt('pys_exc_user', 'ptr', [f'ptr {v.v}'])}"])
    e1 = self.cur
    self.br(l2)
    self.place(l2)
    ph = Ins("phi", "exctype", "")
    self.incoming(ph, nt, e0)
    self.incoming(ph, r, e1)
    r = self.phi(ph)
    self.nn[r] = True
    return Val(r, "exctype")

def gen_exc_tree(self) -> str:
    # the exception classes, builtin and of the program, each with those it is or derives from,
    # itself first ("\2K\1K\1A\1B\1..."): what tells runtime.c's pys_exc_sub whether a class
    # derives from one that a value gives
    if self.exctree == "":
        out: list[str] = []
        for k in EXCBASES:
            out.append("\x02" + k + "\x01" + "\x01".join([b for b in EXCBASES if exc_derives(k, b)]) + "\x01")
        xs = [c for c in self.classes if self.classes[c].exc != ""]
        for c in xs:
            bs = [c] + [x for x in xs if x != c and self.derives(c, x)] + [b for b in EXCBASES if self.derives(c, b)]
            out.append("\x02" + c + "\x01" + "\x01".join(bs) + "\x01")
        self.exctree = self.sconst("".join(out))
    return self.exctree

def gen_exc_sub(self, a: Val, b: Val) -> Val:
    # is a's class (an exception's, or class object a's) class object b's, or derived from it
    r = self.rt("pys_exc_sub", "i64", [f"ptr {a.v}", f"ptr {b.v}", f"ptr {self.exc_tree()}"])
    return self.num_cmp('!=', Val(r, "int"), Val('0', "int"))

def gen_exc_dynamic(self, t: Node) -> bool:
    # is t, isinstance's or issubclass's second argument, a value that holds exception classes
    # (exc_held), or a tuple display of such values and classes named, rather than names alone
    # (exc_classes)
    if t.kind == "tuple":
        held = [x for x in t.kids if x.kind != "starred" and self.exc_held(x)]
        return len(held) > 0 and len(held) + len([x for x in t.kids if self.exc_classes(x)]) == len(t.kids)
    return self.exc_held(t)

def gen_exc_held(self, t: Node) -> bool:
    # does t, a variable or a field of an object a variable holds, hold exception classes (a class
    # object, which may be None, or a tuple of them), as their types say without compiling t; or
    # another expression that is no type, as dry() types it: type(x) of an exception x, which x's
    # type tells (so that type("") keeps isinstance()'s error), a conditional expression whose
    # values hold them or name them, kinds[0], pick(), a.b.c
    v = ""
    x: Node | None = None
    if t.kind == "call":
        x = self.refl_typeof(t)
    if t.kind == "name":
        v = self.static_type(t)
    elif t.kind == "attr" and t.kids[0].kind == "name" and self.dotted(t) == "":
        o = unopt(self.static_type(t.kids[0]))
        v = self.classes[o].ftypes.get(t.s, "") if o in self.classes and t.s not in self.classes[o].methods else ""
    elif x is not None:
        u = unopt(self.dry(x))
        return u == "exc" or (u in self.classes and self.classes[u].exc != "")
    elif t.kind == "ifexp":
        for k in t.kids[1:]:
            if not (k.kind == "name" and self.exc_classes(k)) and not self.exc_held(k):
                return False
        return True
    elif (t.kind == "call" or t.kind == "index" or (t.kind == "attr" and t.s != "__class__")) and self.dotted(t) == "" and not self.puretype(t, False):
        v = self.dry(t)
    return self.exc_holds(v)

def gen_exc_holds(self, t: str) -> bool:
    # is t a class object's type (which may be None), or a tuple's of such items
    u = unopt(t)
    if is_tuple(u):
        return len(targs(u)) > 0 and len([x for x in targs(u) if not self.exc_holds(x)]) == 0
    return u == "exctype"

def gen_exc_test(self, v: Val, t: Node, what: str) -> Val:
    # issubclass(v, t) (what: "issubclass") of a class object v, or isinstance(v, t), t a value
    # (exc_dynamic): a class object, or a tuple of them, of which v's class is one or derives
    # from one, v being an exception (or an object of an exception class of the program). None is
    # an instance of NoneType's class object only (exc_none_class), and a value of another type
    # (a class object, a str) of none. t is evaluated first, as CPython builds its arguments
    # before it tests them, then its classes in turn (exc_any)
    bs = [self.expr(x, "") for x in t.kids] if t.kind == "tuple" else [self.expr(t, "")]
    for b in bs:
        self.exc_flat(b.t, what)
    if what == "issubclass":
        return self.exc_any(v, bs, what)
    u = unopt(v.t)
    xc = u == "exc" or (u in self.classes and self.classes[u].exc != "")
    nul = self.isnull(v)
    if nul == "true":
        return self.exc_any(Val("null", "None"), bs, what)
    if nul == "false":
        return self.exc_any((v if v.t == "exc" else Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc")) if xc else Val("null", ""), bs, what)
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(nul, l2, l1)
    self.place(l1)
    r = self.exc_any((Val(v.v, "exc") if u == "exc" else Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc")) if xc else Val("null", ""), bs, what)
    e1 = self.cur
    self.br(l3)
    self.place(l2)
    rn = self.exc_any(Val("null", "None"), bs, what)
    e2 = self.cur
    self.br(l3)
    self.place(l3)
    ph = Ins("phi", "bool", "")
    self.incoming(ph, r.v, e1)
    self.incoming(ph, rn.v, e2)
    return Val(self.phi(ph), "bool")

def gen_exc_flat(self, t: str, what: str) -> None:
    # are the classes that a value of type t gives isinstance() or issubclass() (what) class
    # objects (or None, which raises TypeError where it is tested): a class object's type, or a
    # tuple's of such items, tuples among them too
    u = unopt(t)
    if is_tuple(u):
        for x in targs(u):
            self.exc_flat(x, what)
    elif u != "exctype" and what == "isinstance":
        self.err("isinstance() is only supported with the builtin types and classes as its second argument")
    elif u != "exctype":
        self.err(f"issubclass() of a class object takes exception classes, or tuples of them, not {typestr(t)}")

def gen_exc_any(self, v: Val, bs: list[Val], what: str) -> Val:
    # does v's class derive from one of the classes bs give isinstance() or issubclass() (what):
    # class objects and tuples of them, tested in turn as CPython tests a tuple's items, where the
    # first that it does stops and None raises TypeError where it is reached. v None is an
    # instance of NoneType's class object only; v of type "", a value of another type, of none:
    # only the raise then
    if v.t == "":
        self.exc_each(v, bs, what, "", Ins("phi", "bool", ""))
        return Val("false", "bool")
    done = self.label()
    ph = Ins("phi", "bool", "")
    self.exc_each(v, bs, what, done, ph)
    self.incoming(ph, "false", self.cur)
    self.br(done)
    self.place(done)
    return Val(self.phi(ph), "bool")

def gen_exc_each(self, v: Val, bs: list[Val], what: str, done: str, ph: Ins) -> Val:
    # exc_any's tests of v against bs in turn, a match branching to done (true, to phi ph); what
    # it returns is v as issubclass() has checked it (arg 1), before the first class it tests
    for b in bs:
        if what == "issubclass" and (is_opt(b.t) or not is_tuple(b.t)):
            v = self.unwrap(v, "TypeError: issubclass() arg 1 must be a class")
        if what == "isinstance":
            b = self.unwrap(b, "TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union")
        else:
            b = self.unwrap(b, "TypeError: issubclass() arg 2 must be a class, a tuple of classes, or a union")
        if is_tuple(b.t):
            v = self.exc_each(v, [self.tget(b, i) for i in range(len(targs(b.t)))], what, done, ph)
        elif v.t != "":
            nxt = self.label()
            self.incoming(ph, "true", self.cur)
            self.cbr((self.ptr_cmp('==', b, self.exc_none_class()) if v.t == "None" else self.exc_sub(v, b)).v, done, nxt)
            self.place(nxt)
    return v

def gen_exc_none_class(self) -> Val:
    # NoneType's class object, which type() gives of an exception that is None: None is its
    # instance, and it derives from no exception class
    r = self.rt("pys_exc_proto", "ptr", [f"ptr {self.sconst('NoneType')}", "ptr null"])
    self.nn[r] = True
    return Val(r, "exctype")

def gen_exc_call(self, c: Val, args: list[Node], how: int = 0) -> Val:
    # c(args) of class object c (an exception class's: exctype), the class evaluated first, then
    # the arguments (one positional argument at most): an object of its class. The function that
    # makes one of a class of the program from the arguments of this call's types is in the table
    # of those types (exc_ctors), which runtime.c's pys_exc_ctor looks c's class up in; a
    # builtin class's object is pys_exc_make's (exc_make). how is 8 for raise c and 16 for raise ...
    # from c: what NoneType's class object (type() of an exception that is None) raises there
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err("a call of an exception class held as a value is supported with positional arguments only")
    if len(args) > 1:
        self.err("a call of an exception class held as a value is supported with one argument at most")
    vals = [self.expr(a, "") for a in args]
    c = self.unwrap(c, "TypeError: 'NoneType' object is not callable")
    sig = vals[0].t if len(vals) > 0 else ""
    if sig not in self.xsigs:
        self.xsigs[sig] = len(self.xsigs)
    fp = self.rt("pys_exc_ctor", "ptr", [f"ptr {c.v}", f"ptr @x.mk.{self.xsigs[sig]}"])
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    self.cbr(self.scalar_cmp('eq', Val(fp, '%ptr'), Val('null', '%ptr')), l2, l1)
    self.place(l1)
    i = Ins("icall", "exc", "")
    i.a = [Val(fp, "env")] + [v for v in vals if v.t != "None"]  # (an argument that is None is not passed)
    if dynamic_program():
        i.a.extend([self.dyn_box(v) for v in vals if numeric_identity(v.t)])
    self.put(i, 1)
    e1 = self.cur
    self.br(l3)
    self.place(l2)
    r2 = self.exc_make(c, vals, how)
    e2 = self.cur
    self.br(l3)
    self.place(l3)
    ph = Ins("phi", "exc", "")
    self.incoming(ph, f"%t{i.r[0]}", e1)
    self.incoming(ph, r2.v, e2)
    r = self.phi(ph)
    self.nn[r] = True
    return Val(r, "exc")

def gen_exc_make(self, c: Val, vals: list[Val], how: int = 0) -> Val:
    # an object of the builtin class of class object c, of the arguments vals (none or one):
    # runtime.c's pys_exc_make, given the argument's str() and repr(), whether it is true (a
    # SyntaxError's traceback line) and its status where it is an int, a bool or None (a
    # SystemExit's code)
    if len(vals) == 0:
        e = self.sconst("")
        return Val(self.rt("pys_exc_make", "ptr", [f"ptr {c.v}", "i64 0", f"ptr {e}", f"ptr {e}", f"i64 {how}", "i64 0"]), "exc")
    v = vals[0]
    s = self.to_str(v).v
    r = self.repr(v).v
    u = unopt(v.t)
    if u in self.classes or is_union(u):
        # (an object whose truth may call its __bool__ or __len__, which CPython calls for no
        # class: tested only where c is of SyntaxError's family, whose traceback line shows it)
        e0 = self.cur
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.exc_sub(c, self.exc_class_value("SyntaxError")).v, l1, l2)
        self.place(l1)
        tv = self.truth(v)
        e1 = self.cur
        self.br(l2)
        self.place(l2)
        ph = Ins("phi", "bool", "")
        self.incoming(ph, "false", e0)
        self.incoming(ph, tv, e1)
        flags = self.select(self.phi(ph), Val("2", "int"), Val("0", "int"))
    else:
        flags = self.select(self.truth(v), Val("2", "int"), Val("0", "int"))
    code = "0"
    if v.t == "int" or v.t == "bool" or v.t == "None" or v.t == BIG:
        flags = self.scalar('or', [Val(flags, "int"), Val("4", "int")])
        code = self.big_status(v).v if v.t != "None" else "0"  # (a promoting int's: bigints.py)
    elif is_sopt(v.t) and (unopt(v.t) == "int" or unopt(v.t) == "bool" or v.t == BIGOPT):
        flags = self.scalar('or', [Val(flags, "int"), Val("4", "int")])
        code = self.big_status(v).v if v.t == BIGOPT else self.optint(v, "0")
    if how != 0:
        flags = self.scalar('or', [Val(flags, "int"), Val(str(how), "int")])
    return Val(self.rt("pys_exc_make", "ptr", [f"ptr {c.v}", "i64 1", f"ptr {s}", f"ptr {r}", f"i64 {flags}", f"i64 {code}"]), "exc")

def gen_exc_ctors(self) -> int:
    # the functions that make an object of each class of the program used as a value (xvals) from
    # the arguments of a call of a class object (none, or one of the type that each form of call,
    # xsigs, has: exc_call), compiled as the program's other functions are, until no more come:
    # a class whose __init__ takes another number of arguments raises CPython's TypeError
    # instead, and one whose __init__ takes another type has none (pys_exc_make raises). A class
    # whose objects are made is one where type() of an exception it may be became a class object
    # (xtypes). How many forms and classes have been seen
    for sig in [x for x in self.xsigs]:
        for c in self.exc_ctor_classes():
            key = f"{self.xsigs[sig]}.{c}"
            if key in self.xctors:
                continue
            ci = self.classes[c]
            init = ci.methods["__init__"] if "__init__" in ci.methods else None
            if ci.bad != "" or (sig != "" and init is not None and len(init.ptypes) > 1 and init.vararg != 1 and not self.exc_ctor_takes(sig, init.ptypes[1])):
                self.xctors[key] = False  # (a class Pystachy cannot make, or whose __init__'s first argument has another type)
                continue
            line = ci.node.line
            noann = mk("noann", "", line, [])
            f = FnInfo(short(c), f"@x.mk.{key}", mk("def", short(c), line, [noann, noann, mk("block", "", line, [])]), "")
            f.params = ["a"] if sig != "" else []
            f.ptypes = [sig] if sig != "" else []
            f.defaults = [noann] if sig != "" else []
            f.dglob = [""] if sig != "" else []
            f.ret = "exc"
            bad = self.exc_ctor_arity(c, 1 if sig != "" else 0)
            self.xctors[key] = True
            if bad != "":
                body = [mk("raise", "", line, [mk("call", "", line, [mk("name", "TypeError", line, []), mk("str", bad, line, [])])])]
            else:
                body = [mk("return", "", line, [mk("excobj", c, line, [mk("name", "a", line, [])] if sig != "" else [])])]
            f.node.kids[2].kids = body
            self.function(f, body)
    return len(self.xctors)

def gen_exc_ctor_classes(self) -> list[str]:
    # the classes of the program that a class object called may be of: those used as values, and
    # those whose objects are made that derive from a class whose objects' type() became one
    out = [x for x in self.xvals]
    for c in self.xcls:
        if c not in self.xvals and ("exc" in self.xtypes or len([t for t in self.xtypes if self.derives(c, t)]) > 0):
            out.append(c)
    return out

def gen_exc_ctor_takes(self, t: str, p: str) -> bool:
    # can an argument of type t be passed for a parameter of type p ("": a template's)
    u = unopt(p)
    if p == "" or t == p or self.widens(t, p) or (is_opt(p) and (t == "None" or t == u or self.widens(t, u))):
        return True
    return (u in self.classes and t == "None") or (is_union(u) and t in umembers(u))

def gen_exc_ctor_arity(self, c: str, n: int) -> str:
    # CPython's TypeError where class c's __init__ cannot take n positional arguments, or ""
    init = self.classes[c].methods["__init__"] if "__init__" in self.classes[c].methods else None
    if init is None:
        return ""  # (BaseException's: any)
    q = f"{short(init.cls)}.__init__()"
    npos = len(init.params) if init.npos < 0 else init.npos
    if n + 1 > npos and init.vararg < 0:
        return f"{q} takes {npos} positional argument{'s' if npos != 1 else ''} but {n + 1} were given"
    for kw in [False, True]:
        # (the positional parameters that no argument fills and that have no default, then the
        # keyword-only ones)
        miss = [init.params[j] for j in range(n + 1, len(init.params)) if j < len(init.defaults) and init.defaults[j].kind == "noann" and j != init.vararg and j != init.kwarg and (init.npos >= 0 and j >= init.npos) == kw]
        what = "keyword-only" if kw else "positional"
        if len(miss) == 1:
            return f"{q} missing 1 required {what} argument: '{miss[0]}'"
        if len(miss) > 1:
            names = ", ".join([f"'{x}'" for x in miss[:-1]]) + f" and '{miss[-1]}'"
            return f"{q} missing {len(miss)} required {what} arguments: {names}"
    return ""

def gen_exc_tables(self) -> None:
    # each form of call of a class object's table of the functions exc_ctors compiled, for
    # runtime.c's pys_exc_ctor: {ExcClass, function} pairs, ended by NULL
    for sig in self.xsigs:
        d = Data("callable", f"@x.mk.{self.xsigs[sig]}")
        for c in self.exc_ctor_classes():
            key = f"{self.xsigs[sig]}.{c}"
            if key in self.xctors and self.xctors[key]:
                d.refs.append(f"@x.{c}")
                d.refs.append(f"@x.mk.{key}")
        d.refs.append("null")
        d.refs.append("null")
        self.consts.append(d)
