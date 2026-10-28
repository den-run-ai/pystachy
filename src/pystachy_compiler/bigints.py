"""Promoting ints: CPython's int in the modules that opt in (# pystachy: python-int).

A promoting int (type BIG) is two words, {lo, hi}, an LLVM {i64, ptr}: hi is null and lo the
value where it fits in 64 bits; otherwise hi is the value's immutable Mpz (runtime.c), which never
fits, and lo is 0. Operations on values that fit run inline as checked 64-bit arithmetic; the
rest, and a step that overflows, call runtime.c's pys_big_* functions, which demote every result
that fits, so equal values have one representation. See docs/python-int.md.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import first_use, local_names
from src.pystachy_compiler.diagnostics import LINES, int_file, int_lists, int_span
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.syntax import Node, made_var, mk
from src.pystachy_compiler.specs import BIG, BIGOPT, CHECKED, IOPS, IRT, RANGEC, READ_HELPERS
from src.pystachy_compiler.utils import bool_for_int, elem, is_dict, is_gen, is_list, is_opt, is_set, is_sopt, is_tuple, is_vtuple, lookable, selem, targs, unopt

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
# The lookups of a dict of int keys (dict_bigkey) by a promoting int key: runtime.c's functions that
# take its {lo, m} (dict_key_args) in place of a 64-bit key's slot
BKEY: dict[str, str] = {
    "pys_dict_get": "pys_dict_bkey_get", "pys_dict_getbox": "pys_dict_bkey_getbox", "pys_dict_pop": "pys_dict_bkey_pop",
    "pys_dict_pop_default": "pys_dict_bkey_pop_default", "pys_dict_popbox": "pys_dict_bkey_popbox",
    "pys_dict_setdefault": "pys_dict_bkey_setdefault", "pys_dict_big_pop": "pys_dict_bkey_big_pop",
    "pys_dict_big_setdefault": "pys_dict_bkey_big_setdefault", "pys_dict_find": "pys_dict_big_find",
}
# A list of ints of a program whose lists hold promoting ints (int_lists: a module opts in, none to
# dynamic Any) holds an item past 64 bits as a tuple does: TSLOT_BIG in its slot, and its Mpz in the
# list's companion (runtime.c's BIGIDS), read only where the slot holds TSLOT_BIG (big_list_value).
# Every module of the program reads a list's int so: one that opts in as a promoting int, another as
# its 64-bit int (NARROW past 64 bits); a promoting int goes into the list as it is from any module
# (big_list_store), and runtime.c's list code keeps the companion in step with the items.
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


def int_tuple(t: str) -> bool:
    # is t a tuple type that holds an int, also in a tuple it holds: one whose ints a list of a
    # program whose lists hold promoting ints holds as promoting ints (held)
    return is_tuple(t) and any([x == "int" or int_tuple(x) for x in targs(t)])


def big_view(t: str) -> str:
    # tuple type t with its ints, also those of the tuples it holds, as promoting ints: the layout of
    # a tuple that a list holds (held), which a tuple of t's 64-bit ints is as it is, unless one of
    # them is -2**63 (big_tuple_view)
    if not is_tuple(t):
        return t
    return "tuple[" + ",".join([BIG if x == "int" else big_view(x) for x in targs(t)]) + "]"


def held(t: str) -> str:
    # the type as which a list of item type t holds its items, and a dict its keys and values and a
    # set its elements of type t: in a program whose lists hold promoting ints (int_lists), a tuple
    # of ints holds them as promoting ints (big_view), which every store gives it (list_hold) and
    # the descriptors of its items say (desc's J, and the key kind's: key_kind); its reads give a
    # module that opts in the promoting ints, and narrow them in another (held_value)
    return big_view(t) if int_lists() and int_tuple(t) else t


def search_type(t: str, et: str) -> str:
    # the type whose descriptor compares the items of a list of t with the value of type et that a
    # search of it takes (in, index(), count(), remove()): the type in which the list holds a tuple
    # of ints (held), for et that tuple's type or the type of it or None; else et
    if et == t:
        return held(t)
    if is_opt(et) and unopt(et) == t and held(t) != t:
        return "opt[" + held(t) + "]"
    return et


def big_tree(t: str) -> bool:
    # is t a builtin value tree of promoting ints, 64-bit ints, floats, bools, strs and None: a tuple,
    # also of tuples, lists and dicts of them, whose value runtime.c's descriptor walks read as
    # compiled code reads it (desc's J: a tuple's promoting int item, its slot and its Mpz word), and
    # whose ==, ordering, hash() and repr() run none of the program's code
    if t == BIG or t in ["int", "float", "bool", "str", "None"]:
        return True
    if is_opt(t):
        return unopt(t) in ["int", "float", "bool", "str"]
    return (is_tuple(t) or is_vtuple(t) or is_list(t) or is_dict(t)) and all([big_tree(x) for x in targs(t)])


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
    # does the module of source line line promote its ints (# pystachy: python-int), or the
    # definition of lib/ that holds it, where a module of the program opts in (int_lists and
    # int_span: specs.INT_HELPERS)
    return int_file(line // LINES) or (int_lists() and int_span(line))


def gen_read_policy(self) -> bool:
    # does a read of a container's int here (a list's item, a dict's key or value, a set's element,
    # also in a tuple of ints that one holds, and a generator's value) give it as the promoting int
    # it is: in a module that opts in (int_policy), and in lib's modules that hand a container's
    # items on as they are (READ_HELPERS: iter()'s iterators, heapq, bisect) where the program's
    # containers hold promoting ints (int_lists); elsewhere the 64-bit int, NARROW past 64 bits
    return self.int_policy(self.line) or (int_lists() and self.curfn.mod in READ_HELPERS)


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


def gen_big_slot(self, raw: str, fn: str, args: list[str], two: bool = False) -> Val:
    # raw, the slot of a list's int, a dict's value or a set's element, as the promoting int it
    # holds: past 64 bits, TSLOT_BIG there (two: or -2**63 + 1, a set's, runtime.c's ssent) and the
    # Mpz that fn(args) reads, which it reads only where the slot holds that (null for -2**63 itself,
    # or -2**63 + 1)
    rare = self.label()
    end = self.label()
    ph = Ins("phi", BIG, "")
    self.incoming(ph, self.big(Val(raw, "int")).v, self.cur)
    if two:
        self.cbr(self.scalar_cmp("sle", Val(raw, "int"), Val("-9223372036854775807", "int")), rare, end)
    else:
        self.cbr(self.scalar_cmp("eq", Val(raw, "int"), Val(TSLOT_BIG, "int")), rare, end)
    self.place(rare)
    w = Val(self.scalar_cast("ptrtoint", Val(self.rt(fn, "ptr", args), "%ptr"), "int"), "int")
    small = self.scalar_cmp("eq", w, Val("0", "int"))  # (-2**63 itself)
    r = self.big(Val(self.select(small, Val(raw if two else TSLOT_BIG, "int"), Val("0", "int")), "int"), self.scalar_cast("inttoptr", w, "%ptr"))
    self.incoming(ph, r.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), BIG)


def gen_big_list_value(self, o: Val, i: str, raw: str) -> Val:
    # raw, the slot of list[int] o at index i (in range, or negative as pys_list_get takes it), as
    # the int that the list holds there (int_lists): a promoting int in a module that opts in, else
    # the 64-bit int, NARROW past 64 bits (big_slot)
    v = self.big_slot(raw, "pys_list_big_at", [f"ptr {o.v}", f"i64 {i}"])
    return v if self.read_policy() else self.big_narrow(v)


def gen_item_type(self, t: str) -> str:
    # the type of the item that a read of list type t gives here (list_value): a promoting int, in
    # a module that opts in, where the program's lists of ints hold them (int_lists), and so a
    # tuple's ints (held)
    if is_list(t) and elem(t) == "int" and int_lists() and self.read_policy():
        return BIG
    if is_list(t) and self.read_policy():
        return held(elem(t))
    return elem(t)


def gen_held_value(self, v: Val) -> Val:
    # v, an item that a list holds as held(v.t) gives it: as that tuple of promoting ints in a
    # module that opts in, else as the tuple of its 64-bit ints, which it is where each fits
    # (NARROW past 64 bits: big_tuple_narrow)
    h = held(v.t)
    if h == v.t:
        return v
    if self.read_policy():
        return Val(v.v, h)
    return self.big_tuple_narrow(Val(v.v, h))


def gen_big_list_store(self, o: Val, v: Val, method: str, index: str) -> None:
    # promoting int v into list[int] o (int_lists): appended, set at index or inserted at index, as
    # the 64-bit int it is where it fits (whose store clears the item's companion entry), else as
    # TSLOT_BIG and its Mpz (pys_list_*_big)
    fits = self.label()
    past = self.label()
    end = self.label()
    pre = [f"ptr {o.v}"] + ([f"i64 {index}"] if index != "" else [])
    self.cbr(self.big_fits([v]), fits, past)
    self.place(fits)
    self.rt({"append": "pys_list_append", "set": "pys_list_set", "insert": "pys_list_insert"}[method], "void", pre + [f"i64 {self.big_lo(v).v}"])
    self.br(end)
    self.place(past)
    self.rt({"append": "pys_list_append_big", "set": "pys_list_set_big", "insert": "pys_list_insert_big"}[method], "void", pre + [f"ptr {self.big_hi(v).v}"])
    self.br(end)
    self.place(end)


def gen_list_coerce(self, v: Val, et: str) -> Val:
    # v as an item of a list of et, or a value of a dict of et: a promoting int stays one where et is
    # int and the program's lists and dicts of ints hold them (int_lists), which list_store and
    # dict_store store as it is (big_list_store, pys_dict_set_big)
    if v.t == BIG and et == "int" and int_lists():
        return v
    return self.coerce(v, et)


def gen_search_hold(self, v: Val, et: str, t: str) -> Val:
    # v as the value of type et that a search of a list of t compares its items with (search_type):
    # a tuple of ints in the layout the list holds its tuples in, as a store gives it (list_hold),
    # also where et is that tuple's type or None and v is not None
    if et == t:
        return self.list_hold(v, t)
    v = self.coerce(v, et)
    if search_type(t, et) == et:
        return v
    some = self.label()
    end = self.label()
    ph = Ins("phi", et, "")
    self.incoming(ph, "null", self.cur)
    self.cbr(self.isnull(v), end, some)
    self.place(some)
    h = self.list_hold(Val(v.v, t), t)
    self.incoming(ph, h.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), et)


def gen_big_items(self, o: Val) -> Val:
    # o.items() of dict o, an int key or value of whose (key, value) tuples is a promoting int, in a
    # program whose lists, dicts and sets of ints hold them (int_lists): pys_dict_big_items makes
    # them with the slots of one (utils.tslots), an int past 64 bits with its Mpz word from the
    # dict's (as pys_dict_big_popitem's); a tuple of ints as the dict holds it, as the list of them
    # holds it (held). Val("", "") for other dicts
    if not int_lists() or "int" not in targs(o.t):
        return Val("", "")
    return Val(self.rt("pys_dict_big_items", "ptr", [f"ptr {o.v}"]), self.ctype("list", [self.ctype("tuple", targs(o.t))]))


def gen_update_pairs(self, d: str, v: Val, kv: list[str]) -> None:
    # dict d, of key and value types kv, updated by v, a list of (key, value) tuples, one insertion
    # per pair: in a program whose lists hold promoting ints (int_lists), an int key or value as the
    # promoting int its pair holds (pys_dict_update_pairs_big); a tuple of ints as it is, as the
    # list and the dict hold it (held)
    if int_lists() and "int" in kv:
        ints = [f"i64 {1 if x == 'int' else 0}" for x in kv]
        self.rt("pys_dict_update_pairs_big", "void", [f"ptr {d}", f"ptr {v.v}"] + ints, self.key_fx(kv[0]))
    else:
        self.rt("pys_dict_update_pairs", "void", [f"ptr {d}", f"ptr {v.v}"], self.key_fx(kv[0]))


def gen_list_hold(self, v: Val, et: str) -> Val:
    # v as an item of a list of et (or a dict's key or value, a set's element), held as held(et): a
    # tuple of promoting ints as it is, and a tuple of 64-bit ints as it is too, but where one of
    # its ints is -2**63 (a new tuple of the held layout, big_tuple_view), as et; else list_coerce
    e = et.replace(BIG, "int")  # (a list's item type, as ctype makes it)
    h = held(e)
    if h == e:
        return self.list_coerce(v, et)
    return Val(self.coerce(v, h).v, e)


def gen_key_hold(self, k: Val, kt: str) -> Val:
    # k, the key that a lookup takes in a dict or set whose keys or elements have type kt, which it
    # holds as held(kt) (dkey): in that layout, as a store gives it (list_hold); a tuple that may be
    # None where it is not None (search_hold: nonekey finds None in no dict), and a tuple that
    # CPython finds as such a key (utils.lookable: a bool for an int, None for a str) in its own
    # type's
    lt = k.t.replace(BIG, "int")
    if is_opt(k.t) and unopt(k.t) == kt:
        return self.search_hold(k, k.t, kt)
    if is_tuple(k.t) and lt != kt and lookable(lt, kt):
        return Val(self.list_hold(k, lt).v, kt)
    return self.list_hold(k, kt)


def gen_dict_key(self, d: Val, e: str) -> Val:
    # the key of entry e of dict d (of a dict of int keys, big_dict_key's; a tuple of ints, which
    # the dict holds as a list holds it, as held_value reads it)
    if self.dict_bigkey(d.t):
        return self.big_dict_key(d, e)
    return self.held_value(self.from_slot(self.rt("pys_dict_key", "i64", [f"ptr {d.v}", f"i64 {e}"]), targs(d.t)[0]))


def gen_dict_int(self, t: str) -> bool:
    # does dict type t hold promoting ints as its values: a dict of ints, in a program whose lists
    # and dicts of ints hold them (int_lists; runtime.c's dbig)
    return is_dict(t) and targs(t)[1] == "int" and int_lists()


def gen_big_dict_value(self, d: Val, e: str, keep: bool = False) -> Val:
    # the value of entry e of d, a dict of ints (dict_int): a promoting int in a module that opts
    # in (or keep), else the 64-bit int, NARROW past 64 bits (big_slot)
    raw = self.rt("pys_dict_val", "i64", [f"ptr {d.v}", f"i64 {e}"])
    v = self.big_slot(raw, "pys_dict_big_val", [f"ptr {d.v}", f"i64 {e}"])
    return v if keep or self.read_policy() else self.big_narrow(v)


def gen_dict_bigkey(self, t: str) -> bool:
    # does dict type t hold promoting ints as its keys: a dict of int keys, in a program whose lists,
    # dicts and sets of ints hold them (int_lists; runtime.c's kbig)
    return is_dict(t) and targs(t)[0] == "int" and int_lists()


def gen_key_coerce(self, k: Val, kt: str) -> Val:
    # k as a key stored into a dict whose keys have type kt (store_key): a promoting int stays one
    # where the keys are ints and the program's dicts hold such keys (int_lists), which dict_put
    # stores as it is
    if k.t == BIG and kt == "int" and int_lists():
        return k
    return self.store_key(k, kt)


def gen_key_slot(self, k: Val) -> str:
    # the slot of key k (key_coerce's) for dict_put, made where d[k] = v made it before the value:
    # none for a promoting int, which dict_put finds by its entry
    return "" if k.t == BIG else self.to_slot(k)


def gen_big_key_entry(self, d: Val, k: Val, fn: str) -> str:
    # the entry of promoting int k as a key of d, a dict of int keys (dict_bigkey), as fn finds it:
    # pys_dict_big_find (-1 where d has none), pys_dict_big_entry (KeyError) or pys_dict_big_put
    # (added with the value 0 where d has none, which its caller stores next)
    return self.rt(fn, "i64", [f"ptr {d.v}"] + self.dict_key_args(k, ""))


def gen_dict_key_args(self, kx: Val, k: str) -> list[str]:
    # the key arguments of a dict lookup by key kx, whose slot is k: a promoting int's {lo, m}, which
    # the functions BKEY names take (kx: a key of a dict of int keys, dict_bigkey)
    if kx.t == BIG:
        return [f"i64 {self.big_lo(kx).v}", f"ptr {self.big_hi(kx).v}"]
    return [f"i64 {k}"]


def gen_dict_key_fn(self, fn: str, kx: Val) -> str:
    # fn, the runtime function of a dict lookup by key kx, or for a promoting int its BKEY twin (also
    # for an int | None one, of a dict of int keys, which is not None there: nonekey, keyed)
    return BKEY[fn] if kx.t == BIG or kx.t == BIGOPT else fn


def gen_big_key(self, k: Val) -> Val:
    # the promoting int key k of a lookup (d[k], del d[k], d[k] op= v), or the one int | None k holds:
    # None is no key of a dict of int keys (KeyError: None, as nonekey raises it)
    if k.t == BIGOPT:
        self.guard(self.isnull(k), "KeyError: None")
        return self.big_unbox(k)
    return k


def gen_dict_put(self, d: Val, k: Val, ks: str, v: Val, kv: list[str]) -> None:
    # d[k] = v of dict d, of key and value types kv, k and v coerced (key_coerce, list_coerce), ks
    # k's slot (key_slot): a promoting int key by its entry, which pys_dict_big_put finds or adds
    if k.t == BIG:
        self.dict_store(d.v, "", v, kv, self.big_key_entry(d, k, "pys_dict_big_put"))
    else:
        self.dict_store(d.v, ks, v, kv)


def gen_dict_value(self, d: Val, e: str) -> Val:
    # the value of entry e of dict d (of a dict of ints, big_dict_value's; a tuple of ints, which the
    # dict holds as a list holds it, as held_value reads it)
    if self.dict_int(d.t):
        return self.big_dict_value(d, e)
    return self.held_value(self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {d.v}", f"i64 {e}"]), targs(d.t)[1]))


def gen_held_read(self, v: Val) -> Val:
    # v, a value of a dict that holds its tuples of ints as a list holds them (held), as held_value
    # reads it; also of one that may be None (get() or pop() with a default that may be None, which
    # held_default holds so too), which holds 64-bit ints: there the tuple of its 64-bit ints, where
    # it is not None (NARROW past 64 bits)
    u = unopt(v.t)
    if not is_opt(v.t) or held(u) == u:
        return self.held_value(v)
    some = self.label()
    end = self.label()
    self.cbr(self.isnull(v), end, some)
    self.place(some)
    self.big_tuple_narrow(Val(v.v, held(u)))
    self.br(end)
    self.place(end)
    return v


def gen_held_default(self, v: Val, et: str, vt: str) -> Val:
    # v as the default of type et (vt, a dict's value type, or vt | None) that get(), pop() or
    # setdefault() of a dict of values of type vt gives or stores: a tuple of ints in the layout in
    # which the dict holds its values (held, search_hold's), else coerced
    if held(vt) == vt:
        return self.coerce(v, et)
    return self.search_hold(v, et, vt)


def gen_held_pair(self, v: Val) -> Val:
    # v, the (key, value) tuple that popitem() of a dict gives (pys_dict_popitem), whose key or value
    # is a tuple of ints that the dict holds as a list holds it (held): in a module that opts in that
    # tuple of promoting ints, elsewhere the tuple of its 64-bit ints (NARROW past 64 bits)
    kv = targs(v.t)
    if held(kv[0]) == kv[0] and held(kv[1]) == kv[1]:
        return v
    t = "tuple[" + held(kv[0]) + "," + held(kv[1]) + "]"
    if self.read_policy():
        return Val(v.v, t)
    return self.big_tuple_narrow(Val(v.v, t))


def gen_big_dict_key(self, d: Val, e: str) -> Val:
    # the key of entry e of d, a dict of int keys (dict_bigkey): a promoting int in a module that opts
    # in, else the 64-bit int, NARROW past 64 bits (big_slot)
    raw = self.rt("pys_dict_key", "i64", [f"ptr {d.v}", f"i64 {e}"])
    v = self.big_slot(raw, "pys_dict_big_key", [f"ptr {d.v}", f"i64 {e}"])
    return v if self.read_policy() else self.big_narrow(v)


def gen_dict_box(self, b: str) -> Val:
    # the slot b of the int | None that get(k) or pop(k, None) of a dict of ints (dict_int) gives,
    # whose box pys_dict_getbox or pys_dict_popbox makes of a value past 64 bits as of a promoting
    # int (pys_big_box): that int | None in a module that opts in, else narrowed
    v = Val(self.from_slot(b, "opt[int]").v, BIGOPT)
    return v if self.read_policy() else self.big_opt_narrow(v)


def gen_big_dict_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of o, a dict of ints whose values may be past 64 bits (dict_int): get(k), get(k, x),
    # pop(k), pop(k, x) and setdefault(k, x) give the promoting int (in a module that does not opt
    # in, the 64-bit int, NARROW past 64 bits), and store or give x, an int, as one; get(k) and
    # pop(k, None) the box of an int | None (dict_box); pop(k) of a bool k raises the KeyError that
    # names it as the bool it is (bool_find). Val("", "") for the rest, which bmethod compiles as for
    # 64-bit values (its 64-bit reads narrow the dict first: NARROWED), but for the box of an
    # int | None (dict_box): a key that may be None but of get(k, x), and a bool key of setdefault()
    # (rejected)
    if any([a.kind == "kw" or a.kind == "starred" or a.kind == "dstar" for a in args]):
        return Val("", "")
    kv = targs(o.t)
    if not ((m == "get" or m == "pop") and len(args) in [1, 2]) and not (m == "setdefault" and len(args) == 2):
        return Val("", "")
    kt = self.dyn_dry(args[0])  # (remembered: a default that is such a call decides it again, dyn_dry)
    dt = self.dyn_dry(args[1]) if len(args) == 2 else ""
    box = (m == "get" and len(args) == 1) or (m == "pop" and dt == "None")
    optbig = kt == BIGOPT and m != "setdefault" and not box  # (an int | None key: big_dict_call)
    if (is_opt(kt) and not optbig and (box or m != "get")) or kt == "None" or (bool_for_int(kt, kv[0]) and m == "setdefault"):
        return Val("", "")
    if len(args) == 2 and not box and dt != "int" and dt != BIG:
        return Val("", "")
    kb = self.expr(args[0], kv[0])
    kx = kb
    if not ((kx.t == BIG or kx.t == BIGOPT) and self.dict_bigkey(o.t)) and not (is_sopt(kx.t) and bool_for_int(unopt(kx.t), kv[0])):
        kx = self.dkey(kx, kv[0])  # (a bool | None, of get(k, x), finds the int key it equals, as in bmethod: keyed)
    k = "" if kx.t == BIG else "0" if kx.t == BIGOPT else self.to_slot(kx)  # (a promoting int key of a dict of int keys: dict_key_args, keyed)
    x = self.key_fx(kv[0])
    if box:
        if len(args) == 2:
            self.expr(args[1], "")
        fn = "pys_dict_getbox" if m == "get" else "pys_dict_popbox"
        return self.dict_box(self.rt(self.dict_key_fn(fn, kx), "i64", [f"ptr {o.v}"] + self.dict_key_args(kx, k) + ["i64 0"], x))
    d = self.to_big(self.expr(args[1], "")) if len(args) == 2 else self.big(Val("0", "int"))
    if m == "pop" and len(args) == 1 and bool_for_int(kb.t, kv[0]):
        self.bool_find(o.v, kb, k)
    return self.big_dict_call(o, m, kx, k, d, len(args) == 2, x)


def gen_big_dict_call(self, o: Val, m: str, kx: Val, k: str, d: Val, has: bool, x: str) -> Val:
    # o.get(kx, d), o.pop(kx[, d]) or o.setdefault(kx, d) of o, a dict of ints (dict_int), its
    # arguments compiled (k: kx's slot, or "" for a promoting int key, dict_key_args; d: the default
    # as a promoting int, has: one was given; x: the lookup's key_fx), for big_dict_method and for
    # fill, where such a call types its dict. An int | None key (BIGOPT) of get() finds no entry
    # where it is None (nonekey), and of pop() raises KeyError: None (big_key) or gives d there
    if m == "pop" and kx.t == BIGOPT and has:
        some = self.label()
        end = self.label()
        ph = Ins("phi", BIG, "")
        self.incoming(ph, d.v, self.cur)
        self.cbr(self.isnull(kx), end, some)
        self.place(some)
        kb = self.big_unbox(kx)
        self.incoming(ph, self.rt(BKEY["pys_dict_big_pop"], BIGLL, [f"ptr {o.v}"] + self.dict_key_args(kb, "") + ["i64 1", f"i64 {self.big_lo(d).v}", f"ptr {self.big_hi(d).v}"], x), self.cur)
        self.br(end)
        self.place(end)
        v = Val(self.phi(ph), BIG)
        return v if self.read_policy() else self.big_narrow(v)
    if m == "pop" and kx.t == BIGOPT:
        kx = self.big_key(kx)
    if m == "get":
        if kx.t == BIG:
            e = self.big_key_entry(o, kx, "pys_dict_big_find")
        else:
            e = self.nonekey(kx, "-1", "pys_dict_find", [f"ptr {o.v}", f"i64 {k}"], x)  # (a key that is None: none)
        found = self.label()
        end = self.label()
        ph = Ins("phi", BIG, "")
        self.incoming(ph, d.v, self.cur)
        self.cbr(self.num_cmp(">=", Val(e, "int"), Val("0", "int")).v, found, end)
        self.place(found)
        self.incoming(ph, self.big_dict_value(o, e, True).v, self.cur)
        self.br(end)
        self.place(end)
        v = Val(self.phi(ph), BIG)
    elif m == "pop":
        v = Val(self.rt(self.dict_key_fn("pys_dict_big_pop", kx), BIGLL, [f"ptr {o.v}"] + self.dict_key_args(kx, k) + [f"i64 {'1' if has else '0'}", f"i64 {self.big_lo(d).v}", f"ptr {self.big_hi(d).v}"], x), BIG)
    else:
        v = Val(self.rt(self.dict_key_fn("pys_dict_big_setdefault", kx), BIGLL, [f"ptr {o.v}"] + self.dict_key_args(kx, k) + [f"i64 {self.big_lo(d).v}", f"ptr {self.big_hi(d).v}"], x), BIG)
    return v if self.read_policy() else self.big_narrow(v)


def gen_big_popitem(self, o: Val) -> Val:
    # o.popitem() of o, a dict of ints or of int keys (dict_int, dict_bigkey), in a module that opts
    # in: its (key, value) tuple of promoting ints, which pys_dict_big_popitem makes with the slots
    # of one (utils.tslots); in other modules, bmethod's pys_dict_popitem raises past 64 bits
    kv = targs(o.t)
    t = self.ctype("tuple", [BIG if kv[0] == "int" else held(kv[0]), BIG if kv[1] == "int" else held(kv[1])])  # (a tuple of ints: held)
    return Val(self.rt("pys_dict_big_popitem", "ptr", [f"ptr {o.v}"], self.key_fx(kv[0])), t)


def gen_dict_store(self, d: str, key: str, v: Val, kv: list[str], e: str = "") -> None:
    # d[k] = v, of dict d of key and value types kv (key: k's slot; e: k's entry, which
    # entry_set writes, where a lookup has found it), v coerced (list_coerce): a promoting int
    # into a dict of ints (dict_int) as pys_dict_set_big stores it, past 64 bits as TSLOT_BIG and
    # its Mpz
    if v.t == BIG and kv[1] == "int" and int_lists():
        b = [f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"]
        if e != "":
            self.rt("pys_dict_entry_set_big", "void", [f"ptr {d}", f"i64 {e}"] + b)
        else:
            self.rt("pys_dict_set_big", "void", [f"ptr {d}", f"i64 {key}"] + b, self.key_fx(kv[0]))
    elif e != "":
        self.rt("pys_dict_entry_set", "void", [f"ptr {d}", f"i64 {e}", "i64 " + self.to_slot(v)])
    else:
        self.rt("pys_dict_set", "void", [f"ptr {d}", f"i64 {key}", "i64 " + self.to_slot(v)], self.key_fx(kv[0]))


def gen_set_int(self, t: str) -> bool:
    # does set type t hold promoting ints as its elements: a set or frozenset of ints, in a program
    # whose lists, dicts and sets of ints hold them (int_lists; runtime.c's sbig)
    return is_set(t) and selem(t) == "int" and int_lists()


def gen_big_set_value(self, s: Val, j: str) -> Val:
    # the element in slot j of s, a set of ints (set_int): a promoting int in a module that opts in,
    # else the 64-bit int, NARROW past 64 bits (big_slot)
    raw = self.rt("pys_set_key", "i64", [f"ptr {s.v}", f"i64 {j}"])
    v = self.big_slot(raw, "pys_set_big_key", [f"ptr {s.v}", f"i64 {j}"], True)
    return v if self.read_policy() else self.big_narrow(v)


def gen_set_value(self, s: Val, j: str) -> Val:
    # the element in slot j of set s (of a set of ints, big_set_value's; a tuple of ints, which the
    # set holds as a list holds it, as held_value reads it)
    if self.set_int(s.t):
        return self.big_set_value(s, j)
    return self.held_value(self.from_slot(self.rt("pys_set_key", "i64", [f"ptr {s.v}", f"i64 {j}"]), selem(s.t)))


def gen_set_coerce(self, v: Val, et: str) -> Val:
    # v as an element added to a set of et (store_elem): a promoting int stays one where the set's
    # elements are ints (et int, or a promoting int's type, whose set ctype makes one of ints) and
    # the program's sets of ints hold them (int_lists), which set_store adds as it is
    et = "int" if et == BIG else et
    if v.t == BIG and et == "int" and int_lists():
        return v
    return self.store_elem(v, et)


def gen_set_store(self, s: str, v: Val, et: str) -> None:
    # set s, whose elements have type et, adds v, which set_coerce has made one: a promoting int as
    # pys_set_big_add adds it, past 64 bits as TSLOT_BIG and its Mpz
    if v.t == BIG:
        self.rt("pys_set_big_add", "void", [f"ptr {s}", f"i64 {self.big_lo(v).v}", f"ptr {self.big_hi(v).v}"])
        return
    self.rt("pys_set_add", "void", [f"ptr {s}", "i64 " + self.to_slot(v)], self.key_fx(et))


def gen_big_set_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of o, a set of ints whose elements may be past 64 bits (set_int): pop() gives the
    # promoting int (in a module that does not opt in, the 64-bit int, NARROW past 64 bits), and
    # discard(x) and remove(x) of a promoting int x, or of an int | None x (None is no element:
    # discard() does nothing, remove() raises KeyError: None), look for it exactly
    # (pys_set_big_*); Val("", "") for the rest, which smethod compiles as for 64-bit ints
    if m == "pop" and len(args) == 0:
        v = Val(self.rt("pys_set_big_pop", BIGLL, [f"ptr {o.v}"]), BIG)
        return v if self.read_policy() else self.big_narrow(v)
    if (m == "discard" or m == "remove") and len(args) == 1 and args[0].kind not in ["kw", "starred", "dstar"] and self.dyn_dry(args[0]) in [BIG, BIGOPT]:
        x = self.expr(args[0], "")
        fn = "pys_set_big_discard" if m == "discard" else "pys_set_big_remove"
        end = ""
        if x.t == BIGOPT:
            if m == "remove":
                self.guard(self.isnull(x), "KeyError: None")
            else:
                some = self.label()
                end = self.label()
                self.cbr(self.isnull(x), end, some)
                self.place(some)
            x = self.big_unbox(x)
        self.rt(fn, "void", [f"ptr {o.v}", f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}"])
        if end != "":
            self.br(end)
            self.place(end)
        return Val("null", "None")
    return Val("", "")


def gen_big_list_minmax(self, o: Val, maximum: bool) -> Val:
    # min() or max() of list[int] o (int_lists): the promoting int, narrowed in a module that does not
    # opt in
    v = Val(self.rt("pys_list_big_minmax", BIGLL, [f"ptr {o.v}", f"i64 {1 if maximum else 0}"]), BIG)
    return v if self.read_policy() else self.big_narrow(v)


def gen_big_list_find(self, o: Val, x: Val, op: int, st: str, en: str) -> Val:
    # x in o (op 0: the index, or -1), o.count(x) (1), o.index(x, st, en) (2) or o.remove(x) (3) of
    # list[int] o (int_lists) and x a promoting int or a float, which an item past 64 bits may equal:
    # exactly (pys_list_big_find)
    if x.t == "float":
        args = ["i64 " + self.to_slot(x), "ptr null", "i64 1"]
    else:
        x = self.to_big(x)
        args = [f"i64 {self.big_lo(x).v}", f"ptr {self.big_hi(x).v}", "i64 0"]
    return Val(self.rt("pys_list_big_find", "i64", [f"ptr {o.v}"] + args + [f"i64 {op}", f"i64 {st}", f"i64 {en}"]), "int")


def gen_big_list_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # o.m(args) of list[int] o in a program whose lists hold promoting ints (int_lists): pop() and
    # pop(i) give the promoting int (big_list_value's), append(x) and insert(i, x) of a promoting int
    # store it (big_list_store), and index(), count() and remove() of a promoting int or a float look
    # for it exactly (big_list_find); Val("", "") for the rest, which bmethod compiles as for 64-bit
    # ints (runtime.c's searches skip the items past 64 bits, which equal no 64-bit int)
    if any([a.kind == "kw" or a.kind == "starred" or a.kind == "dstar" for a in args]):
        return Val("", "")
    ints = ["int", "bool", BIG]
    if m == "pop" and len(args) <= 1 and (len(args) == 0 or self.dry(args[0]) in ints):
        i = self.as_int(self.expr(args[0], "")) if len(args) == 1 else Val("-1", "int")
        v = Val(self.rt("pys_list_big_pop", BIGLL, [f"ptr {o.v}", f"i64 {i.v}"]), BIG)
        return v if self.read_policy() else self.big_narrow(v)
    if ((m == "append" and len(args) == 1) or (m == "insert" and len(args) == 2 and self.dry(args[0]) in ints)) and self.dry(args[-1]) == BIG:
        i = self.as_int(self.expr(args[0], "")) if m == "insert" else Val("", "")
        self.list_store(o, self.expr(args[-1], ""), m, i.v)
        return Val("null", "None")
    if m in ["index", "count", "remove"] and len(args) >= 1 and len(args) <= (3 if m == "index" else 1) and self.dry(args[0]) in [BIG, "float"]:
        if not all([self.dry(a) in ints for a in args[1:]]):
            return Val("", "")
        x = self.expr(args[0], "")
        bounds = [self.as_int(self.expr(a, "")).v for a in args[1:]] + ["0", "9223372036854775807"][len(args) - 1 :]
        r = self.big_list_find(o, x, {"count": 1, "index": 2, "remove": 3}[m], bounds[0], bounds[1])
        return Val("null", "None") if m == "remove" else r
    return Val("", "")


def gen_big_len(self, v: Val) -> Val:
    # promoting int v, the result of an object's __len__, as the 64-bit length that CPython's
    # slot_sq_length takes: ValueError where it is negative (past 64 bits too), then OverflowError
    # where it does not fit
    self.guard(self.big_cmp("<", v, Val("0", "int")).v, "ValueError: __len__() should return >= 0")
    self.guard(self.scalar("xor", [Val(self.big_fits([v]), "bool"), Val("true", "bool")]), "OverflowError: cannot fit 'int' into an index-sized integer")
    return self.big_lo(v)


def gen_big_hashed(self, v: Val) -> Val:
    # promoting int v, the result of an object's __hash__, as the hash that CPython's slot_tp_hash
    # takes: v where it fits in 64 bits, else int's hash of it (the caller makes -1 -2)
    return Val(self.select(self.big_fits([v]), self.big_lo(v), self.big_hash(v)), "int")


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
    if (op == "in" or op == "not in") and a.t == BIG and is_list(b.t) and elem(b.t) == "int" and int_lists():
        # (a list of ints may hold one past 64 bits: exactly)
        return self.num_cmp(">=" if op == "in" else "<", self.big_list_find(b, a, 0, "0", "0"), Val("0", "int"))
    if (op == "in" or op == "not in") and a.t == BIG and self.dict_bigkey(b.t):
        # (a dict of int keys may hold one past 64 bits: its entry, exactly)
        return self.num_cmp(">=" if op == "in" else "<", Val(self.big_key_entry(b, a, "pys_dict_big_find"), "int"), Val("0", "int"))
    if (op == "in" or op == "not in") and a.t == BIG and self.set_int(b.t):
        # (a set of ints may hold one past 64 bits: by CPython's hash, exactly)
        hit = Val(self.rt("pys_set_big_has", "i64", [f"ptr {b.v}", f"i64 {self.big_lo(a).v}", f"ptr {self.big_hi(a).v}"]), "int")
        return self.num_cmp("!=" if op == "in" else "==", hit, Val("0", "int"))
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
