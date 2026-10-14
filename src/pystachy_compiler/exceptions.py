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
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import Exit, FnInfo, Ins, Try, Val
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.specs import (
    EXCBASES,
    EXCEPTIONS,
    EXCKW,
    PYBUILTINS,
    exc_base_of,
    exc_derives,
    is_excname,
)
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    is_const,
    is_opt,
    is_sopt,
    is_tuple,
    lt,
    meet,
    pure_arg,
    targs,
    typestr,
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
    ends: list[dict[str, bool]] = []
    # the try notes the depth of the unwind actions (pys_exc_begin runs those added since) and
    # the exception being handled, which every way out of its clauses restores
    mark = Val(self.rt("pys_try_mark", "i64", []), "int")
    old = self.rt("pys_exc_handled", "ptr", [])
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
            for c in h.kids[0].kids if h.kids[0].kind == "tuple" else [h.kids[0]] if h.kids[0].kind == "name" else h.kids[:0]:
                self.modchk(c)  # (read through an import that may have raised)
                if (c.chk or self.foreign(c.s)) and c.s in self.gflag and c.s in self.classes:
                    # a class whose class statement may not have run yet
                    self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{c.s}.def')}, true"), self.unbound(c.s))
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
                self.rt("pys_exc_restore", "void", [f"ptr {old}"])
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
            self.emit(f"store ptr {e.v}, ptr {sl}")
            self.emit(f"store i64 {len(fx.conts)}, ptr {fx.sel}")
            fx.conts.append(self.label())
            self.br(fx.entry)
            self.place(fx.conts[-1])
            self.throw(Val(self.ins(f"load ptr, ptr {sl}"), "exc"))
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
        self.emit(f"store i64 {len(fx.conts)}, ptr {fx.sel}")
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
        ksel = self.ins(f"load i64, ptr {fx.sel}")
        for j in range(len(fx.conts) - 1):
            nx = self.label()
            self.cbr(self.ins(f"icmp eq i64 {ksel}, {j}"), fx.conts[j], nx)
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

def gen_unnarrowed(self, bodies: list[list[Node]]) -> dict[str, bool]:
    # a copy of narrowed without the names that the code of bodies binds or deletes: what
    # holds wherever an exception may come from in them
    out: dict[str, bool] = {}
    if len(self.narrowed) > 0:
        names: dict[str, bool] = {}
        for b in bodies:
            collect(b, names)
            deleted(b, names)
        for nm in self.narrowed:
            if nm not in names:
                out[nm] = True
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
            return Val(self.ins(f"icmp ne ptr {v.v}, null") if yes and v.v not in self.nn else "true" if yes else "false", "bool")
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
        if c.kind != "name" or c.s in self.ltype or c.s in self.gtypes or c.s in self.funcs or c.s in self.assigned:
            self.err("an except clause needs exception classes: a name, or a tuple of names")
        if c.s in self.unsupported:
            self.err(self.unsupported[c.s])
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
    x = self.ins(f"load ptr, ptr {slot}")
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
        self.emit(f"store i1 false, ptr {self.lflag[name]}")
    elif name != "" and name not in self.ltype and name in self.gflag:
        self.emit(f"store i1 false, ptr @g.{name}.def")
    for s in self.shadows:
        if s[0] == name and s[3] != "":
            self.emit(f"store i1 false, ptr {s[3]}")
        elif s[0] == name and s[1] == "" and name in self.gflag:
            self.emit(f"store i1 false, ptr @g.{name}.def")

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
    oe = exc_base_of(name, "OSError")
    if npos > 1 and EXCEPTIONS[name] != "" and not (oe and npos <= 3):
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

def gen_cause(self, c: Node) -> None:
    # raise ... from c: c is evaluated and checked (an exception class, a call of one, an
    # exception or None: else CPython's TypeError is raised instead), and otherwise ignored:
    # only a traceback would show it
    if c.kind == "None":
        return
    k = self.exc_class(c)
    if k == "" or k in self.classes:
        v = self.exc_value_of(c, k)
        if v.t != "exc" and v.t != "None" and not (v.t in self.classes and self.classes[v.t].exc != ""):
            self.raise_("TypeError", self.sconst("exception causes must derive from BaseException"))
            self.place(self.label())  # (what follows, the raise itself, is never reached)
        return
    self.exc_vals(self.exc_args(c), c.kids[0].s if c.kind == "call" else "")

def gen_exc_value_of(self, e: Node, k: str) -> Val:
    # the value of e, the exception of a raise statement, unless it is a builtin exception class
    # or a call of one: a class of the program k (or a call of it) makes an object of it
    if k == "":
        return self.expr(e, "")
    if self.classes[k].exc == "":
        self.err(f"'{short(k)}' is not an exception class: exceptions must derive from BaseException")
    self.class_ready(e.kids[0] if e.kind == "call" else e)  # (looked up first, as a call of it does)
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
    if k == "" or k in self.classes:
        v = self.exc_value_of(e, k)
        if v.t in self.classes and self.classes[v.t].exc != "":
            v = self.exc_of(v)
        if v.t != "exc":
            self.err("exceptions must derive from BaseException: raise needs an exception class or a call of one")
        if len(n.kids) > 1:
            self.cause(n.kids[1])
        self.throw(v)
        return
    name = e.kids[0].s if e.kind == "call" else e.s
    vals = self.exc_vals(self.exc_args(e), name)
    if len(n.kids) > 1:
        self.cause(n.kids[1])
    if n.s == "init":
        # a module's raise of ImportError at its top level (Loader.init_raise()): under an optional
        # import (a "guard" in a uimport) the module returns, not imported, so that the importer's
        # handler runs and a later import runs its code again
        g = self.curfn.ll + ".guard"
        self.global_var(g, "i1")
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.ins(f"load i1, ptr {g}"), l1, l2)
        self.place(l1)
        self.emit(f"store i1 false, ptr {self.curfn.ll}.done")
        self.ret_(Val("null", "None"))
        self.place(l2)
    if name == "SystemExit":
        self.exit_(vals, False)
        return
    if self.eh:
        self.throw(self.exc_value("OSError" if name == "IOError" or name == "EnvironmentError" else name, vals))
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
    if name == "OSError" and (no.t == "int" or no.t == "bool"):
        kind = self.rt("pys_exc_errcls", "ptr", [f"i64 {self.as_int(no).v}"])
    elif name == "OSError" and is_sopt(no.t) and (unopt(no.t) == "int" or unopt(no.t) == "bool"):
        # (an errno that may be None: OSError itself if it is)
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(self.isnull(no), l1, l2)
        self.place(l1)
        self.br(l3)
        self.place(l2)
        k = self.rt("pys_exc_errcls", "ptr", [f"i64 {self.as_int(self.deref(no)).v}"])
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
    elif len(vals) > 1 and exc_base_of(name, "OSError"):
        oe = self.os_error(name, vals)
        return Val(self.rt("pys_exc_new", "ptr", [f"ptr {oe[0]}", f"ptr {oe[1]}", f"ptr {oe[2]}"]), "exc")
    elif len(vals) > 1:
        msg = self.repr(self.tuple_(vals)).v
        args = self.rt("pys_str_slice", "ptr", [f"ptr {msg}", "i64 1", "i64 -1"])
    elif len(vals) == 1:
        msg = (self.repr(vals[0]) if name == "KeyError" else self.to_str(vals[0])).v
        if vals[0].t != "str" and name != "KeyError":
            args = self.repr(vals[0]).v  # (a KeyError's message is its argument's repr already)
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
    elif vals[0].t == "int" or vals[0].t == "bool":
        self.rt("pys_exit", "void", [f"i64 {self.as_int(vals[0]).v}"])
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
    if len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool" or vals[0].t == "None"):
        s = self.to_str(vals[0]).v
        return Val(self.rt("pys_exc_exit", "ptr", [f"i64 {self.as_int(vals[0]).v if vals[0].t != 'None' else '0'}", f"ptr {s}", f"ptr {s}"]), "exc")
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
    size = f"ptrtoint (ptr getelementptr (%C.{c}, ptr null, i32 1) to i64)"
    o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), c)
    self.nn[o.v] = True
    self.xcls[c] = True
    self.setfield(o, self.field(o, " cls"), " cls", Val(f"@x.{c}", "str"))
    # (with an __init__ of the program, an OSError's args are left empty, and a SystemExit's
    # code None, until its super().__init__() sets them, as OSError.__new__ and SystemExit.__init__ do)
    self.exc_keep(o, vals if init is None or not self.derives(c, "OSError") else vals[:0], init is None)
    self.class_defaults(o)
    self.line = line
    if init is not None:
        self.call_fn(init, [o] + vals, kws)
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
            if not is_const(ci.fdefault[fl]):
                self.class_default(h, fl)  # (compiled before the class statement runs)
            v = Val(self.ins(f"load {lt(t)}, ptr {h.fglob[fl]}"), t) if fl in h.fglob else self.coerce(self.expr(ci.fdefault[fl], t), t)
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
        if t == "int" or t == "bool":
            code = self.as_int(vals[0]).v
        if t != "":
            # (an int | None or a bool | None is a status, 0 if it is None; another value that
            # may be None is one only if it is None)
            st = t == "int" or t == "bool" or t == "None" or (is_sopt(t) and (unopt(t) == "int" or unopt(t) == "bool"))
            hc = "true" if st else self.isnull(vals[0]) if t in self.classes or is_opt(t) else "false"
        self.setfield(o, self.field(o, " code"), " code", Val(code, "int"))
        self.setfield(o, self.field(o, " hc"), " hc", Val(hc, "bool"))
        if is_sopt(t) and (unopt(t) == "int" or unopt(t) == "bool"):
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.isnull(vals[0]), l2, l1)
            self.place(l1)
            self.setfield(o, self.field(o, " code"), " code", self.as_int(self.deref(vals[0])))
            self.place(l2)

def gen_exc_of(self, v: Val) -> Val:
    # the exception that raises exception object v
    self.notnone(v, "TypeError: exceptions must derive from BaseException")
    return Val(self.rt("pys_exc_user", "ptr", [f"ptr {v.v}"]), "exc")

def gen_exc_brepr(self, o: Val) -> Val:
    # BaseException.__repr__ of exception object o: the name of its class, and its args
    a = self.getfield(o, self.field(o, " args"), " args")
    return Val(self.rt("pys_exc_brepr", "ptr", [f"ptr {o.v}", f"ptr {a.v}"]), "str")

def gen_super_call(self, sc: Node, m: str, args: list[Node], based: bool = False) -> Val:
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
        if bm.deco != "" and not based:
            # a static or class method of the base gets no object (Base.m(self, ...) passes
            # self as its first argument), and a class method's cls would be the object's class
            self.cls_bound(bm, cls, True)
            return self.call_fn(bm, [], args, direct=True)
        return self.call_fn(bm, [me], args, direct=True)
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
    ex = f"ptr @x.exit.{c}" if len(bodies) == 3 else "ptr null"
    self.consts.append(f"@x.{c} = private constant {{ptr, ptr, ptr, ptr, ptr}} {{ptr {self.sconst(c)}, ptr {self.sconst(shown(c))}, ptr @x.str.{c}, ptr @x.repr.{c}, {ex}}}")

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
