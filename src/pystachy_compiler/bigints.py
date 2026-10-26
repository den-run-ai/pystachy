"""Promoting ints: CPython's int in the modules that opt in (# pystachy: python-int).

A promoting int (type BIG) is two words, {lo, hi}, an LLVM {i64, ptr}: hi is null and lo the
value where it fits in 64 bits; otherwise hi is the value's immutable Mpz (runtime.c), which never
fits, and lo is 0. Operations on values that fit run inline as checked 64-bit arithmetic; the
rest, and a step that overflows, call runtime.c's pys_big_* functions, which demote every result
that fits, so equal values have one representation. See docs/python-int.md.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import LINES, int_file
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.specs import BIG, CHECKED, IOPS, RANGEC
from src.pystachy_compiler.utils import elem, is_dict, is_list, is_set, is_tuple, is_vtuple, selem, targs

# pys_big_op's operation codes (pys_mpz_binop's, then shifts and **)
BIGOPS: dict[str, int] = {"+": 0, "-": 1, "*": 2, "//": 3, "%": 4, "&": 5, "|": 6, "^": 7, "<<": 8, ">>": 9, "**": 10}
BIGLL = "{i64, ptr}"
# the operators whose result an int of a module that opts in may need past 64 bits for: two ints
# take them as promoting ints (% & | ^ >> of two 64-bit values always fit)
PROMOTES: list[str] = ["+", "-", "*", "//", "<<", "**"]
# where a promoting int past 64 bits goes into 64-bit storage (a container, a tuple, an int
# parameter of a module that does not opt in): CPython's message for an int too big for a C long
NARROW = "OverflowError: Python int too large to convert to C long"


def narrowed(ts: list[str]) -> list[str]:
    # the types ts as members of an annotation's container, tuple or union, which hold 64-bit ints
    return ["int" if t == BIG else t for t in ts]


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
    # a op b of ints, bools and promoting ints, as CPython's int computes it: + - * & | ^ inline
    # where both fit (and + - * do not overflow), everything else through pys_big_op
    x = self.to_big(a)
    y = self.to_big(b)
    if op == "/":
        return self.big_truediv(x, y)
    if op not in BIGOPS:
        self.err(f"unsupported operand type(s) for {op}: 'int' and 'int'")
    if op not in CHECKED and op not in IOPS:
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
    else:
        v = self.big(Val(self.scalar(IOPS[op], [lx, ly]), "int"))
    self.incoming(ph, v.v, self.cur)
    self.br(end)
    self.place(slow)
    w = self.big_call(op, x, y)
    self.incoming(ph, w.v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), BIG)


def gen_big_truediv(self, x: Val, y: Val) -> Val:
    # x / y: both fit, CPython's correctly rounded int / int; past 64 bits, not yet (#907)
    self.guard(self.scalar("xor", [Val(self.big_fits([x, y]), "bool"), Val("true", "bool")]), "NotImplementedError: true division of an int past 64 bits is not supported yet in python-int modules")
    return Val(self.rt("pys_idiv", "double", [f"i64 {self.big_lo(x).v}", f"i64 {self.big_lo(y).v}"]), "float")


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
    if name == "pow" and n == 2 and t in nums and vals[1].t in nums:
        return self.big_arith("**", vals[0], vals[1])
    if (name == "min" or name == "max") and n >= 2 and all([v.t in nums for v in vals]):
        # (the first of equal values, as CPython keeps it)
        best = self.to_big(vals[0])
        for v in vals[1:]:
            x = self.to_big(v)
            better = self.big_cmp("<" if name == "min" else ">", x, best)
            best = Val(self.select(better.v, x, best), BIG)
        return best
    return Val("", "")
