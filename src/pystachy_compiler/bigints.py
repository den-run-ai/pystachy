"""Promoting ints: CPython's int in the modules that opt in (# pystachy: python-int).

A promoting int (type BIG) is two words, {lo, hi}, an LLVM {i64, ptr}: hi is null and lo the
value where it fits in 64 bits; otherwise hi is the value's immutable Mpz (runtime.c), which never
fits, and lo is 0. Operations on values that fit run inline as checked 64-bit arithmetic; the
rest, and a step that overflows, call runtime.c's pys_big_* functions, which demote every result
that fits, so equal values have one representation. See docs/python-int.md.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import first_use, local_names
from src.pystachy_compiler.diagnostics import LINES, int_file
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.syntax import Node, made_var, mk
from src.pystachy_compiler.specs import BIG, BIGOPT, CHECKED, IOPS, IRT, RANGEC
from src.pystachy_compiler.utils import elem, is_dict, is_gen, is_list, is_set, is_tuple, is_vtuple, selem, targs

# pys_big_op's operation codes (pys_mpz_binop's, then shifts and **)
BIGOPS: dict[str, int] = {"+": 0, "-": 1, "*": 2, "//": 3, "%": 4, "&": 5, "|": 6, "^": 7, "<<": 8, ">>": 9, "**": 10}
BIGLL = "{i64, ptr}"
# the operators whose result an int of a module that opts in may need past 64 bits for: two ints
# take them as promoting ints (% & | ^ >> of two 64-bit values always fit)
PROMOTES: list[str] = ["+", "-", "*", "//", "<<", "**"]
# where a promoting int past 64 bits goes into 64-bit storage (a list, dict or set, a union, an int
# parameter of a module that does not opt in): CPython's message for an int too big for a C long
NARROW = "OverflowError: Python int too large to convert to C long"
# A tuple's promoting int item (utils.tslots) holds its value in the item's slot where it fits, but
# for -2**63: there, and for a value past 64 bits, the slot holds TSLOT_BIG, and the item's Mpz word
# (0 for -2**63) is read too (big_item). A tuple of 64-bit ints none of which is -2**63 is so a
# tuple of promoting ints as it is (big_tuple_view).
TSLOT_BIG = "-9223372036854775808"
# An int | None of a module that opts in (BIGOPT) is a box, as an opt[int] is: null for None, else
# runtime.c's pys_box of the value, whose second word is null, where it fits; past 64 bits, a box
# of TSLOT_BIG and its Mpz (pys_big_box). So an opt[int] is one as it is, and one of a value that
# fits is the opt[int] of it, which 64-bit storage takes once a test has found no Mpz (big_opt_narrow)


def narrows(a: str, b: str) -> bool:
    # does a value of type a become one of type b by a test (a promoting int into 64-bit storage,
    # big_narrow, which raises; a tuple whose items promote differently, big_tuple_view): a
    # conversion that branches (Gen.convert_at)
    if b == "" or a == b:
        return False
    return a == BIG or a == BIGOPT or (is_tuple(a) and (BIG in a or BIG in b))


def big_viewable(a: str, b: str) -> bool:
    # are tuple types a and b the same but for promoting ints against 64-bit ints, also in their
    # tuples' items: their slots agree (utils.tslots), so a tuple of one is one of the other as it
    # is, but for big_tuple_view's tests
    if not is_tuple(a) or not is_tuple(b) or a == b:
        return False
    x = targs(a)
    y = targs(b)
    if len(x) != len(y):
        return False
    for i in range(len(x)):
        if x[i] != y[i] and not (x[i] == "int" and y[i] == BIG) and not (x[i] == BIG and y[i] == "int") and not big_viewable(x[i], y[i]):
            return False
    return True


def narrowed(ts: list[str]) -> list[str]:
    # the types ts as members of an annotation's container, tuple or union, which hold 64-bit ints
    # (also as an int | None: BIGOPT)
    return ["int" if t == BIG else "opt[int]" if t == BIGOPT else t for t in ts]


# Where a bool and the int it equals give the same results and errors (bool_numeric): arithmetic,
# whose methods are the int's (& | ^ of two bools give a bool), and builtins that take a number but
# none that may return it as it is
NUMOPS = ["+", "-", "*", "/", "//", "%", "**", "<<", ">>"]
NUMCALLS = ["int", "float", "abs", "round", "hash", "bool", "range", "chr", "hex", "oct", "bin"]


def gen_bool_numeric(self, f: FnInfo, j: int) -> bool:
    # does function f read its parameter j only as a number, where a bool and the int it equals give
    # the same results and errors: then a bool argument is the promoting int it equals (pcoerce),
    # which CPython's output cannot tell apart; elsewhere it is rejected, as in a module that does
    # not opt in (it would print as 1, not True)
    if f.node.kind != "def" or len(f.node.kids) < 3 or f.extern or j >= len(f.params) or j == f.vararg or j == f.kwarg:
        return False
    body = f.node.kids[2]
    if first_use(body, {"locals": True, "vars": True, "eval": True, "exec": True}, False) is not None:
        return False  # (which read it by no name)
    nums = [f.params[k] for k in range(len(f.params)) if k < len(f.ptypes) and f.ptypes[k] in [BIG, "int", "float", "bool"]]
    names: dict[str, bool] = {}
    local_names(body.kids, names)
    calls: list[str] = []
    for nm in NUMCALLS if f.clo < 0 else []:
        # (the builtins, which neither f nor the program binds, see numeric_proof; a closure's
        # names may be those of the functions around it)
        if nm not in names and nm not in f.params and nm not in self.mvars and nm not in self.gtypes and nm not in self.funcs and nm not in self.classes and nm not in self.aliases and nm not in self.fglobals:
            calls.append(nm)
    return numeric_reads(body, "", f.params[j], nums, calls)


def yields(e: Node, name: str) -> bool:
    # may expression e's value be name's value itself, not one computed from it
    if e.kind == "name":
        return e.s == name
    if e.kind == "boolop":
        return yields(e.kids[0], name) or yields(e.kids[1], name)
    if e.kind == "ifexp":
        return yields(e.kids[1], name) or yields(e.kids[2], name)
    if e.kind == "walrus":
        return yields(e.kids[0], name)
    return False


def numeric(e: Node, nums: list[str]) -> bool:
    # is expression e a number, whose methods are none of the program's: a literal, a parameter of
    # nums (an int, a float or a bool), not of anything, or arithmetic of numbers
    if e.kind == "int" or e.kind == "float" or e.kind == "True" or e.kind == "False" or (e.kind == "name" and e.s in nums):
        return True
    if e.kind == "unary":
        return e.s == "not" or numeric(e.kids[0], nums)
    if e.kind == "binop" and (e.s in NUMOPS or e.s == "&" or e.s == "|" or e.s == "^"):
        return numeric(e.kids[0], nums) and numeric(e.kids[1], nums)
    return False


def numeric_store(t: Node, name: str, nums: list[str], calls: list[str]) -> bool:
    # does store target t read name only as a number (bool_numeric): storing to a name reads none,
    # and a subscript's key is no number's place (a dict keeps the bool it takes as a new key)
    if t.kind == "name":
        return True
    if t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        return all([numeric_store(e, name, nums, calls) for e in t.kids])
    return all([not yields(e, name) and numeric_reads(e, "", name, nums, calls) for e in t.kids])


def numeric_reads(n: Node, ctx: str, name: str, nums: list[str], calls: list[str]) -> bool:
    # does code n read name only as a number (bool_numeric), n's value going to ctx: "num" (an
    # operand that only computes with it), "test" (its truth) or "" (anything else)
    k = n.kind
    if k == "name":
        return n.s != name or ctx != ""
    if k in ["def", "lambda", "class", "subclass", "listcomp", "asynccomp", "setcomp", "dictcomp"]:
        return first_use(n, {name: True}, False) is None  # (a scope of its own, which this does not follow)
    if k == "binop":
        a = n.kids[0]
        b = n.kids[1]
        if n.s in NUMOPS:
            # (another object's method would take the bool: the other operand is a number)
            if (yields(a, name) and not numeric(b, nums)) or (yields(b, name) and not numeric(a, nums)):
                return False
        elif n.s == "&" or n.s == "|" or n.s == "^":
            if (yields(a, name) and b.kind != "int") or (yields(b, name) and a.kind != "int"):
                return False
        elif yields(a, name) or yields(b, name):
            return False
        return numeric_reads(a, "num", name, nums, calls) and numeric_reads(b, "num", name, nums, calls)
    if k == "unary":
        # (~ of a bool warns that it is deprecated)
        return numeric_reads(n.kids[0], "test" if n.s == "not" else "" if n.s == "~" else "num", name, nums, calls)
    if k == "boolop":
        return numeric_reads(n.kids[0], ctx, name, nums, calls) and numeric_reads(n.kids[1], ctx, name, nums, calls)
    if k == "ifexp":
        return numeric_reads(n.kids[0], "test", name, nums, calls) and numeric_reads(n.kids[1], ctx, name, nums, calls) and numeric_reads(n.kids[2], ctx, name, nums, calls)
    if k == "cmp":
        ops = n.s.split(",")
        for i in range(len(n.kids)):
            if yields(n.kids[i], name):
                # (compared with numbers alone: no __eq__ or __contains__ of the program's takes it)
                for op in ops[max(i - 1, 0) : i + 1]:
                    if op == "is" or op == "is not" or op == "in" or op == "not in":
                        return False
                if (i > 0 and not numeric(n.kids[i - 1], nums)) or (i + 1 < len(n.kids) and not numeric(n.kids[i + 1], nums)):
                    return False
            if not numeric_reads(n.kids[i], "num", name, nums, calls):
                return False
        return True
    if k == "call" and n.kids[0].kind == "name" and n.kids[0].s in calls:
        for a in n.kids[1:]:
            if a.kind == "starred" or a.kind == "dstar" or not numeric_reads(a.kids[0] if a.kind == "kw" else a, "num", name, nums, calls):
                return False
        return True
    if k == "if" or k == "while":
        return all([numeric_reads(n.kids[i], "test" if i == 0 else "", name, nums, calls) for i in range(len(n.kids))])
    if k == "assert":
        return numeric_reads(n.kids[0], "test", name, nums, calls) and all([numeric_reads(e, "", name, nums, calls) for e in n.kids[1:]])
    if k == "assign" or k == "annassign":
        ts = n.kids[:-1] if k == "assign" else n.kids[:1]
        if not all([numeric_store(t, name, nums, calls) for t in ts]):
            return False
        return (k == "annassign" and len(n.kids) < 3) or numeric_reads(n.kids[-1], "", name, nums, calls)
    if k == "augassign":
        t = n.kids[0]
        v = n.kids[1]
        if t.kind == "name" and t.s == name:
            # (name op= v reads name as op's operand)
            ok = (n.s in NUMOPS and numeric(v, nums)) or ((n.s == "&" or n.s == "|" or n.s == "^") and v.kind == "int")
            return ok and numeric_reads(v, "num", name, nums, calls)
        if yields(v, name) and not (n.s in NUMOPS and numeric(t, nums)):
            return False
        return numeric_store(t, name, nums, calls) and numeric_reads(v, "num", name, nums, calls)
    if k == "for":
        return numeric_store(n.kids[0], name, nums, calls) and all([numeric_reads(e, "", name, nums, calls) for e in n.kids[1:]])
    return all([numeric_reads(e, "", name, nums, calls) for e in n.kids])


def gen_int_policy(self, line: int) -> bool:
    # does the module of source line line promote its ints (# pystachy: python-int)
    return int_file(line // LINES)


def gen_big(self, lo: Val, hi: str = "null") -> Val:
    # the promoting int of 64-bit int lo, or of Mpz pointer hi (lo 0)
    i = Ins("big.make", BIG, "")
    i.a = [Val(lo.v, "int"), Val(hi, "%ptr")]
    self.put(i, 2)
    return Val(f"%t{i.r[1]}", BIG)


def gen_big_lo(self, v: Val) -> Val:
    i = Ins("big.lo", "int", "")
    i.a = [v]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", "int")


def gen_big_hi(self, v: Val) -> Val:
    i = Ins("big.hi", "%ptr", "")
    i.a = [v]
    self.put(i, 1)
    return Val(f"%t{i.r[0]}", "%ptr")


def gen_to_big(self, v: Val) -> Val:
    # v, an int, bool or promoting int, as a promoting int
    if v.t == BIG:
        return v
    return self.big(self.as_int(v))


def gen_big_fits(self, vs: list[Val]) -> str:
    # an i1, true where every promoting int of vs fits in 64 bits (its hi is null)
    h = Val(self.scalar_cast("ptrtoint", self.big_hi(vs[0]), "int"), "int")
    for v in vs[1:]:
        h = Val(self.scalar("or", [h, Val(self.scalar_cast("ptrtoint", self.big_hi(v), "int"), "int")]), "int")
    return self.scalar_cmp("eq", h, Val("0", "int"))


def gen_big_call(self, op: str, x: Val, y: Val) -> Val:
    # pys_big_op(x, y, op): the general case, which demotes its result
    return Val(self.rt("pys_big_op", BIGLL, [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}", f"i64 {self.big_lo(y).v}", f"ptr {self.big_hi(y).v}", f"i64 {BIGOPS[op]}"]), BIG)


def gen_big_arith(self, op: str, a: Val, b: Val) -> Val:
    # a op b of ints, bools and promoting ints, as CPython's int computes it: inline where both
    # fit (+ - * that do not overflow, & | ^, // by other than -1, %, >>, and << that keeps its
    # bits), everything else through pys_big_op, whose result's Mpz is null where big_known
    # proves it fits: LLVM then drops the tests of later operations on it where it can fold that
    x = self.to_big(a)
    y = self.to_big(b)
    if op == "/":
        return self.big_truediv(x, y)
    if op not in BIGOPS:
        self.err(f"unsupported operand type(s) for {op}: 'int' and 'int'")
    if op == "**":
        return self.big_call(op, x, y)
    fast = self.label()
    slow = self.label()
    end = self.label()
    ph = Ins("phi", BIG, "")
    self.cbr(self.big_fits([x, y]), fast, slow)
    self.place(fast)
    lx = self.big_lo(x)
    ly = self.big_lo(y)
    if op in CHECKED:
        r = self.checked(op, lx.v, ly.v)
        done = self.label()
        self.cbr(r[1], slow, done)
        self.place(done)
        v = self.big(Val(r[0], "int"))
    elif op in IOPS:
        v = self.big(Val(self.scalar(IOPS[op], [lx, ly]), "int"))
    elif op == "<<":
        # (a count of 0 to 63 whose shift loses no bits: shifting back gives x)
        counted = self.label()
        self.cbr(self.scalar_cmp("ult", ly, Val("64", "int")), counted, slow)
        self.place(counted)
        r0 = Val(self.scalar("shl", [lx, ly]), "int")
        done = self.label()
        self.cbr(self.scalar_cmp("eq", Val(self.scalar("ashr", [r0, ly]), "int"), lx), done, slow)
        self.place(done)
        v = self.big(r0)
    elif op == "//":
        # (MIN // -1 is 2**63: pys_big_op's; pys_floordiv raises CPython's ZeroDivisionError)
        done = self.label()
        self.cbr(self.scalar_cmp("ne", ly, Val("-1", "int")), done, slow)
        self.place(done)
        v = self.big(Val(self.rt("pys_floordiv", "i64", [f"i64 {lx.v}", f"i64 {ly.v}"]), "int"))
    else:
        # % and >>: pys_mod and pys_shr, whose results fit (and errors are CPython's)
        v = self.big(Val(self.rt(IRT[op], "i64", [f"i64 {lx.v}", f"i64 {ly.v}"]), "int"))
    self.incoming(ph, v.v, self.cur)
    self.br(end)
    self.place(slow)
    w = self.big_call(op, x, y)
    known = self.big_known(op, x, y)
    if known != "":
        lw = self.big_lo(w)
        if op == "&":
            # (r & m is r for an operand m that bounds it: LLVM learns r's range from a constant m)
            for v in [x, y]:
                pos = Val(self.scalar("and", [Val(self.big_fits([v]), "bool"), Val(self.scalar_cmp("sge", self.big_lo(v), Val("0", "int")), "bool")]), "bool")
                lw = Val(self.scalar("and", [lw, Val(self.select(pos.v, self.big_lo(v), Val("-1", "int")), "int")]), "int")
        w = self.big(lw, self.select(known, Val("null", "%ptr"), self.big_hi(w)))
    self.incoming(ph, w.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), BIG)


def gen_big_known(self, op: str, x: Val, y: Val) -> str:
    # an i1 that is true where x op y fits in 64 bits whatever the other operand: x % y of a y that
    # fits (|r| < |y|), x >> y of an x that fits, and x & y of an operand that fits and is not
    # negative (0 <= r <= it); "" for the other operators
    if op == "%":
        return self.big_fits([y])
    if op == ">>":
        return self.big_fits([x])
    if op != "&":
        return ""
    ok: list[str] = []
    for v in [x, y]:
        pos = Val(self.scalar_cmp("sge", self.big_lo(v), Val("0", "int")), "bool")
        ok.append(self.scalar("and", [Val(self.big_fits([v]), "bool"), pos]))
    return self.scalar("or", [Val(ok[0], "bool"), Val(ok[1], "bool")])


def gen_big_truediv(self, x: Val, y: Val) -> Val:
    # x / y, rounded once as CPython rounds int / int (pys_idiv where both fit)
    return Val(self.rt("pys_big_truediv", "double", [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}", f"i64 {self.big_lo(y).v}", f"ptr {self.big_hi(y).v}"]), "float")


def gen_big_unary(self, op: str, v: Val) -> Val:
    # -v, +v and ~v of a promoting int (or of an int or bool, in a module that opts in)
    x = self.to_big(v)
    if op == "+":
        return x
    if op == "~":
        # (~x is x ^ -1, which never overflows 64 bits)
        return self.big_arith("^", x, self.big(Val("-1", "int")))
    return self.big_arith("-", self.big(Val("0", "int")), x)


def gen_big_abs(self, v: Val) -> Val:
    x = self.to_big(v)
    neg = self.big_cmp("<", x, self.big(Val("0", "int")))
    yes = self.label()
    end = self.label()
    ph = Ins("phi", BIG, "")
    self.incoming(ph, x.v, self.cur)
    self.cbr(neg.v, yes, end)
    self.place(yes)
    r = self.big_unary("-", x)
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), BIG)


def gen_big_cmp(self, op: str, a: Val, b: Val) -> Val:
    # a op b (== != < <= > >=) of ints, bools and promoting ints: inline where both fit, else
    # pys_big_cmp's -1, 0 or 1
    x = self.to_big(a)
    y = self.to_big(b)
    fast = self.label()
    slow = self.label()
    end = self.label()
    ph = Ins("phi", "bool", "")
    self.cbr(self.big_fits([x, y]), fast, slow)
    self.place(fast)
    r = self.num_cmp(op, self.big_lo(x), self.big_lo(y))
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(slow)
    c = Val(self.rt("pys_big_cmp", "i64", [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}", f"i64 {self.big_lo(y).v}", f"ptr {self.big_hi(y).v}"]), "int")
    s = self.num_cmp(op, c, Val("0", "int"))
    self.incoming(ph, s.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


def gen_big_float_cmp(self, op: str, a: Val, b: Val) -> Val:
    # a op b of a promoting int and a float, exactly, as CPython compares them
    swap = a.t == "float"
    x = self.to_big(b if swap else a)
    d = b if not swap else a
    c = Val(self.rt("pys_big_cmp_float", "i64", [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}", f"double {d.v}"]), "int")
    # (2: a NaN, which is unordered: only != holds)
    if op == "!=":
        return self.num_cmp("!=", c, Val("0", "int"))
    nan = self.num_cmp("==", c, Val("2", "int"))
    rel = {"==": "==", "<": ">" if swap else "<", "<=": ">=" if swap else "<=", ">": "<" if swap else ">", ">=": "<=" if swap else ">="}[op]
    r = self.num_cmp(rel, c, Val("0", "int"))
    return Val(self.scalar("and", [r, Val(self.scalar("xor", [nan, Val("true", "bool")]), "bool")]), "bool")


def gen_big_truth(self, v: Val) -> str:
    # nonzero: a value with an Mpz never is zero
    h = Val(self.scalar_cast("ptrtoint", self.big_hi(v), "int"), "int")
    return self.scalar_cmp("ne", Val(self.scalar("or", [self.big_lo(v), h]), "int"), Val("0", "int"))


def gen_big_str(self, v: Val) -> Val:
    return Val(self.rt("pys_big_str", "ptr", [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]), "str")


def gen_big_hash(self, v: Val) -> Val:
    return Val(self.rt("pys_big_hash", "i64", [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]), "int")


def gen_big_float(self, v: Val) -> Val:
    return Val(self.rt("pys_big_float", "double", [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]), "float")


def gen_big_narrow(self, v: Val) -> Val:
    # a promoting int as a 64-bit int, for 64-bit storage: past 64 bits, OverflowError
    if v.t != BIG:
        return v
    self.guard(self.scalar("xor", [Val(self.big_fits([v]), "bool"), Val("true", "bool")]), NARROW)
    return self.big_lo(v)


def gen_big_box(self, v: Val) -> Val:
    # promoting int v as an int | None (BIGOPT): its box
    return Val(self.rt("pys_big_box", "ptr", [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]), BIGOPT).identity(v)


def gen_big_unbox(self, v: Val) -> Val:
    # the promoting int that int | None v, known not to be None, holds: its box's two words, an Mpz
    # where the second is not null (whose value's first word is 0)
    lo = Val(self.mload("int", v.v), "int")
    w = Val(self.mload("int", self.maddr("int", v.v, "1")), "int")
    small = self.scalar_cmp("eq", w, Val("0", "int"))
    return self.big(Val(self.select(small, lo, Val("0", "int")), "int"), self.scalar_cast("inttoptr", w, "%ptr")).identity(v)


def gen_big_opt_narrow(self, v: Val) -> Val:
    # int | None v of a module that opts in as one of a 64-bit int, for 64-bit storage: the same box,
    # where None or a value that fits; past 64 bits, OverflowError (NARROW)
    if v.t != BIGOPT:
        return v
    if v.v == "null" or v.v == "undef":
        return Val(v.v, "opt[int]")
    test = self.label()
    end = self.label()
    self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, test)
    self.place(test)
    w = Val(self.mload("int", self.maddr("int", v.v, "1")), "int")
    self.guard(self.scalar_cmp("ne", w, Val("0", "int")), NARROW)
    self.br(end)
    self.place(end)
    return Val(v.v, "opt[int]").identity(v)


def gen_big_opt_str(self, v: Val) -> Val:
    # str() and repr() of int | None v of a module that opts in: "None", or its promoting int's
    some = self.label()
    end = self.label()
    ph = Ins("phi", "str", "")
    self.incoming(ph, self.sconst("None"), self.cur)
    self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
    self.place(some)
    r = self.big_str(self.big_unbox(v))
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "str")


def gen_big_opt_hash(self, v: Val) -> Val:
    # hash() of int | None v of a module that opts in: None's (Gen.hash_value), or its promoting int's
    some = self.label()
    end = self.label()
    ph = Ins("phi", "int", "")
    self.incoming(ph, str(0xFCA86420), self.cur)
    self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
    self.place(some)
    r = self.big_hash(self.big_unbox(v))
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "int")


def gen_big_opt_or(self, v: Val, none: str) -> Val:
    # the promoting int that int | None v of a module that opts in holds, or the int none where v is
    # None
    nv = self.to_big(Val(none, "int"))
    e0 = self.cur
    some = self.label()
    end = self.label()
    self.cbr(self.ptr_cmp("!=", v, Val("null", "None")).v, some, end)
    self.place(some)
    b = self.big_unbox(v)
    e1 = self.cur
    self.br(end)
    self.place(end)
    ph = Ins("phi", BIG, "")
    self.incoming(ph, nv.v, e0)
    self.incoming(ph, b.v, e1)
    return Val(self.phi(ph), BIG)


def gen_big_status(self, v: Val) -> Val:
    # an int, a bool or a promoting int v, or an int | None of a module that opts in (None: 0), as a
    # 64-bit status, a SystemExit's code or the errno that names an OSError's class: past 64 bits -1,
    # as CPython's SystemExit takes an int too large for a C long long (which names no errno)
    if v.t == BIGOPT:
        v = self.big_opt_or(v, "0")
    if v.t != BIG:
        return self.as_int(v)
    return Val(self.select(self.big_fits([v]), self.big_lo(v), Val("-1", "int")), "int")


def gen_big_tuple_narrow(self, v: Val) -> Val:
    # tuple v, whose items (or its tuples' items) may be promoting ints, as the tuple of their 64-bit
    # ints: the same tuple, whose first slots are that tuple's (tslots), where each fits; else
    # OverflowError, as a promoting int going into 64-bit storage raises (NARROW)
    ts = targs(v.t)
    for i in range(len(ts) if v.v != "undef" else 0):
        if ts[i] == BIG:
            self.big_narrow(self.tget(v, i))
        elif is_tuple(ts[i]) and BIG in ts[i]:
            self.big_tuple_narrow(self.tget(v, i))
    return Val(v.v, v.t.replace(BIG, "int"))


def gen_big_item(self, v: Val, lo: Val, k: int, j: str) -> Val:
    # the promoting int item of tuple v whose slot holds lo. Its Mpz word, slot k (or, for the item
    # at run-time index j of a tuple of promoting ints, the slot j past the items), is read only
    # where lo is TSLOT_BIG: a tuple of 64-bit ints that big_tuple_view made one has no slot there
    rare = self.label()
    end = self.label()
    ph = Ins("phi", BIG, "")
    self.incoming(ph, self.big(lo).v, self.cur)
    self.cbr(self.scalar_cmp("eq", lo, Val(TSLOT_BIG, "int")), rare, end)
    self.place(rare)
    if j == "":
        w = self.tslot(v, k)
    else:
        w = Val(self.mload("int", self.maddr("int", v.v, self.scalar("add", [Val(j, "int"), Val(str(len(targs(v.t))), "int")]))), "int")
    small = self.scalar_cmp("eq", w, Val("0", "int"))  # (-2**63 itself)
    r = self.big(Val(self.select(small, Val(TSLOT_BIG, "int"), Val("0", "int")), "int"), self.scalar_cast("inttoptr", w, "%ptr"))
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), BIG)


def gen_big_view_test(self, v: Val, t: str) -> str:
    # an i1, true where tuple v cannot be a t as it is (big_tuple_view) since one of its 64-bit ints
    # that t holds as a promoting int is -2**63; its promoting ints that t holds as 64-bit ints
    # are narrowed (OverflowError past 64 bits)
    a = targs(v.t)
    b = targs(t)
    acc = "false"
    for i in range(len(a)):
        c = "false"
        if a[i] == "int" and b[i] == BIG:
            c = self.scalar_cmp("eq", self.tget(v, i), Val(TSLOT_BIG, "int"))
        elif a[i] == BIG and b[i] == "int":
            self.big_narrow(self.tget(v, i))
        elif a[i] != b[i]:
            c = self.big_view_test(self.tget(v, i), b[i])  # (a tuple item: the same test)
        if c != "false":
            acc = c if acc == "false" else self.scalar("or", [Val(acc, "bool"), Val(c, "bool")])
    return acc


def gen_big_tuple_view(self, v: Val, t: str) -> Val:
    # tuple v as tuple type t, which differs from its type only in promoting ints against 64-bit
    # ints (also in its tuples' items): the same tuple, as their slots agree (tslots), unless a
    # 64-bit int that t holds as a promoting int is -2**63, whose slot would say to read an Mpz
    # word the tuple lacks (TSLOT_BIG): then a new tuple of t's layout, item by item
    if v.v == "undef":
        return Val(v.v, t)
    copy = self.big_view_test(v, t)
    if copy == "false":
        return Val(v.v, t)
    rare = self.label()
    end = self.label()
    ph = Ins("phi", t, "")
    self.incoming(ph, v.v, self.cur)
    self.cbr(copy, rare, end)
    self.place(rare)
    c = self.tuple_([self.coerce(self.tget(v, i), targs(t)[i]) for i in range(len(targs(t)))])
    self.incoming(ph, c.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), t)


def gen_big_tuple_repr(self, v: Val) -> Val:
    # repr() of a tuple whose items (or its tuples' items) may be promoting ints, as CPython
    # writes a tuple: the runtime's repr reads 64-bit ints (desc), so the items' are joined here
    ts = targs(v.t)
    parts = [Val(self.sconst("("), "str")]
    for i in range(len(ts)):
        if i > 0:
            parts.append(Val(self.sconst(", "), "str"))
        parts.append(self.repr(self.tget(v, i)))
    parts.append(Val(self.sconst(",)" if len(ts) == 1 else ")"), "str"))
    return self.concat(parts)


def gen_big_tuple_hash(self, v: Val) -> Val:
    # hash() of such a tuple, as CPython's tuplehash (xxHash's mixing, runtime.c's htuple) mixes
    # its items' hashes, a promoting int's CPython's (big_hash)
    ts = targs(v.t)
    acc = Val("2870177450012600261", "int")
    for i in range(len(ts)):
        lane = self.hash_value(self.tget(v, i))
        acc = Val(self.scalar("add", [acc, Val(self.scalar("mul", [lane, Val("-4417276706812531889", "int")]), "int")]), "int")  # (14029467366897019727)
        acc = Val(self.scalar("or", [Val(self.scalar("shl", [acc, Val("31", "int")]), "int"), Val(self.scalar("lshr", [acc, Val("33", "int")]), "int")]), "int")
        acc = Val(self.scalar("mul", [acc, Val("-7046029288634856825", "int")]), "int")  # (11400714785074694791)
    acc = Val(self.scalar("add", [acc, Val(str(len(ts) ^ 2870177450012600261 ^ 3527539), "int")]), "int")
    return Val(self.select(self.scalar_cmp("eq", acc, Val("-1", "int")), Val("1546275796", "int"), acc), "int")


def gen_big_parse(self, s: Val, base: Val) -> Val:
    # int(s, base) in a module that opts in
    return Val(self.rt("pys_big_from_str", BIGLL, [f"ptr {s.v}", f"i64 {base.v}"]), BIG)


def gen_big_literal(self, text: str) -> Val:
    # an int literal past 64 bits: decimal, or 0x, 0o or 0b as the parser keeps it in a module that
    # opts in (Parser.exact_ints), maybe negated
    digits = text[1:] if text.startswith("-") else text
    return self.big_parse(Val(self.sconst(text), "str"), Val("0" if digits.startswith("0") and len(digits) > 1 else "10", "int"))


def gen_big_binop(self, op: str, a: Val, b: Val) -> Val:
    # a op b where an operand is a promoting int, or both are ints of a module that opts in: the
    # result, or Val("", "") where the 64-bit operation is CPython's (% & | ^ >> never overflow,
    # / of two ints gives a float)
    nums = ["int", "bool", BIG]
    if a.t in nums and b.t in nums:
        if a.t != BIG and b.t != BIG and op not in PROMOTES:
            return Val("", "")
        if a.t == "bool" and b.t == "bool" and op in IOPS:
            return Val("", "")
        return self.big_arith(op, a, b)
    if a.t == "float" or b.t == "float":
        # (the int converted to float first, as CPython does; OverflowError past the float range)
        return self.arith(op, self.as_float(a), self.as_float(b))
    if a.t == BIGOPT or b.t == BIGOPT:
        return Val("", "")  # (an int | None's TypeError for None, or its promoting int: Gen.arith)
    # (another operand: a sequence's repetition count, or an object's operator method, take a 64-bit int)
    return self.arith(op, self.big_narrow(a), self.big_narrow(b))


def gen_big_compare(self, op: str, a: Val, b: Val) -> Val:
    # a op b where an operand is a promoting int
    nums = ["int", "bool", BIG]
    if op in ["==", "!=", "<", "<=", ">", ">="]:
        if a.t in nums and b.t in nums:
            return self.big_cmp(op, a, b)
        if (a.t == "float" and b.t in nums) or (b.t == "float" and a.t in nums):
            return self.big_float_cmp(op, a, b)
        o = b.t if a.t == BIG else a.t
        if (op == "==" or op == "!=") and (o == "None" or o == "str" or o == "bytes" or is_list(o) or is_dict(o) or is_set(o) or is_tuple(o) or is_vtuple(o)):
            return Val("false" if op == "==" else "true", "bool")  # (never equal to an int)
    if (op == "is" or op == "is not") and (a.t == "None" or b.t == "None"):
        return Val("false" if op == "is" else "true", "bool")  # (a promoting int is never None)
    if op == "is" or op == "is not":
        self.err("'is' between ints is not supported in python-int modules yet")
    if (op == "in" or op == "not in") and a.t == BIG and int_items(b.t):
        # an int of 64-bit storage equals a value that fits in 64 bits: its lo (a float item may
        # equal one past 64 bits, so other containers take the value narrowed, as other operands do)
        found = self.cmp2("in", self.big_lo(a), b)
        hit = Val(self.scalar("and", [Val(self.big_fits([a]), "bool"), found]), "bool")
        return hit if op == "in" else Val(self.scalar("xor", [hit, Val("true", "bool")]), "bool")
    return self.cmp2(op, self.big_narrow(a), self.big_narrow(b))


def int_items(t: str) -> bool:
    # are the items of container t (its keys, of a dict) ints or bools
    ints = ["int", "bool"]
    if is_list(t):
        return elem(t) in ints
    if is_set(t):
        return selem(t) in ints
    if is_dict(t) or is_vtuple(t):
        return targs(t)[0] in ints
    if is_tuple(t):
        return all([x in ints for x in targs(t)])
    return t == RANGEC


def gen_big_method(self, v: Val, m: str) -> Val:
    # v.bit_length() and v.bit_count() of a promoting int, or Val("", "") for another method (Gen.bmethod
    # gives it the 64-bit value)
    if m == "bit_length" or m == "bit_count":
        fn = "pys_big_bit_length" if m == "bit_length" else "pys_big_bit_count"
        return Val(self.rt(fn, "i64", [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]), "int")
    return Val("", "")


def gen_big_builtin(self, name: str, vals: list[Val]) -> Val:
    # builtin name(vals) where a value is a promoting int, or int() in a module that opts in: the
    # result, or Val("", "") where the builtin takes 64-bit ints (Gen.builtin narrows them)
    nums = ["int", "bool", BIG]
    n = len(vals)
    t = vals[0].t if n > 0 else ""
    if name == "abs" and n == 1 and t in nums:
        return self.big_abs(vals[0])
    if name == "int" and n == 1:
        if t == BIG:
            return vals[0]
        if t == "str":
            return self.big_parse(vals[0], Val("10", "int"))
        if t == "float":
            return Val(self.rt("pys_big_from_float", BIGLL, [f"double {vals[0].v}"]), BIG)
        return Val("", "")
    if name == "int" and n == 2 and t == "str" and vals[1].t in nums:
        return self.big_parse(vals[0], self.as_int(vals[1]))
    if name == "float" and n == 1 and t == BIG:
        return self.big_float(vals[0])
    if (name == "str" or name == "repr") and n == 1 and t == BIG:
        return self.big_str(vals[0])
    if name == "hash" and n == 1 and t == BIG:
        return self.big_hash(vals[0])
    if name == "bool" and n == 1 and t == BIG:
        return Val(self.big_truth(vals[0]), "bool")
    if name == "round" and n == 1 and t == BIG:
        return vals[0]
    if name == "sum" and n == 2 and vals[1].t == BIG and (self.iter_object(t) or is_gen(t)):
        # (an iterator's or a generator's items, added as they come: reduce)
        item = made_var("__item", self.line)
        return self.reduce(name, [mk("listcomp", "gen", self.line, [item, item, self.vnode(vals[0])]), self.vnode(vals[1])], BIG)
    if name == "sum" and 1 <= n <= 2 and is_list(t) and (elem(t) == "int" or elem(t) == "bool") and (n == 1 or vals[1].t == "int" or vals[1].t == BIG):
        # (64-bit items added past 64 bits, from an int start; a bool start is rejected below)
        sv = self.to_big(vals[1] if n == 2 else Val("0", "int"))
        return Val(self.rt("pys_big_sum", BIGLL, [f"ptr {vals[0].v}", f"i64 {self.big_lo(sv).v}", f"ptr {self.big_hi(sv).v}"]), BIG)
    if name == "pow" and n == 2 and t in nums and vals[1].t in nums:
        return self.big_arith("**", vals[0], vals[1])
    if name == "divmod" and n == 2 and t in nums and vals[1].t in nums:
        # (x // y first: its ZeroDivisionError is divmod's; a tuple holds promoting ints, tslots)
        return self.tuple_([self.big_arith("//", vals[0], vals[1]), self.big_arith("%", vals[0], vals[1])])
    if name == "divmod" and n == 2 and (t == "float" or vals[1].t == "float") and t in nums + ["float"] and vals[1].t in nums + ["float"]:
        # (with a float: both as floats first, the int rounded once, as CPython's float_divmod)
        dn = self.as_float(vals[0])
        dd = self.as_float(vals[1])
        self.guard(self.scalar_cmp('oeq', Val(dd.v, 'float'), Val('0.0', 'float')), "ZeroDivisionError: float divmod()")
        return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
    if name == "pow" and n == 3 and all([v.t in nums for v in vals]) and BIG in [v.t for v in vals]:
        xs = [self.to_big(v) for v in vals]
        args = []
        for x in xs:
            args += [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}"]
        return Val(self.rt("pys_big_powmod", BIGLL, args), BIG)
    if (name == "hex" or name == "oct" or name == "bin") and n == 1 and t == BIG:
        return self.format_(vals[0], mk("str", "#" + ("x" if name == "hex" else name[0]), self.line, []))
    if (name == "min" or name == "max") and n >= 2 and all([v.t == "int" or v.t == BIG for v in vals]):
        # (the first of equal values, as CPython keeps it; with a bool, which CPython may give as it
        # is, they are compiled as in a module that does not opt in: Gen.builtin)
        best = self.to_big(vals[0])
        for v in vals[1:]:
            x = self.to_big(v)
            better = self.big_cmp("<" if name == "min" else ">", x, best)
            best = Val(self.select(better.v, x, best), BIG)
        return best
    return Val("", "")
