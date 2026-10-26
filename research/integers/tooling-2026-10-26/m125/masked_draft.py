def wraps(e: Node) -> bool:
    # an int tree whose result's low 64 bits depend only on its operands' low 64 bits: +, -, * and
    # << (which wrapping 64-bit arithmetic computes exactly in those bits), under &, | and ^
    if e.kind != "binop":
        return False
    if e.s == "+" or e.s == "-" or e.s == "*" or e.s == "<<":
        return True
    return (e.s == "&" or e.s == "|" or e.s == "^") and (wraps(e.kids[0]) or wraps(e.kids[1]))


def gen_flag_or(self, a: str, b: str) -> str:
    if a == "false":
        return b
    if b == "false":
        return a
    return self.scalar("or", [Val(a, "bool"), Val(b, "bool")])


def gen_flag_and(self, a: str, b: str) -> str:
    if a == "false" or b == "false":
        return "false"
    return self.scalar("and", [Val(a, "bool"), Val(b, "bool")])


def gen_masked(self, n: Node, want: str) -> Val:
    # x & y where a side wraps (#125): that side is computed in wrapping 64-bit arithmetic, which
    # keeps the exact result's low 64 bits, with a flag for "a step overflowed". x & y needs no
    # other bits where the other side is exact and not negative, so CPython's result is the low
    # bits'. Otherwise OverflowError, as the overflowing step raises today (now after the whole
    # expression is evaluated, where CPython would have gone on with a bigger int).
    a = self.wexpr(n.kids[0], want)
    b = self.wexpr(n.kids[1], a[0].t)
    if a[0].t != "int" or b[0].t != "int" or a[0].v == "undef" or b[0].v == "undef":
        self.overflow_if(self.flag_or(a[1], b[1]))
        return self.arith("&", a[0], b[0])
    x = a[0]
    y = b[0]
    xneg = self.sign_flag(x)
    yneg = self.sign_flag(y)
    self.overflow_if(self.flag_or(self.flag_and(a[1], self.flag_or(b[1], yneg)), self.flag_and(b[1], xneg)))
    return Val(self.scalar("and", [Val(x.v, "int"), Val(y.v, "int")]), "int")


def gen_sign_flag(self, v: Val) -> str:
    # "v < 0", decided at compile time for a literal
    if v.lit or v.v.lstrip("-").isdigit():
        return "true" if v.v.startswith("-") else "false"
    return self.scalar_cmp("slt", Val(v.v, "int"), Val("0", "int"))


def gen_overflow_if(self, bad: str) -> None:
    if bad != "false":
        self.guard(bad, "OverflowError: integer result does not fit in 64 bits")


def gen_wexpr(self, e: Node, want: str) -> tuple[Val, str]:
    # (value, flag) of e in wrapping 64-bit arithmetic where wraps(e) (see gen_masked): the flag is
    # "false" or an i1 that is true where the value holds only the exact result's low 64 bits
    if not wraps(e):
        return (self.expr(e, want), "false")
    a = self.wexpr(e.kids[0], want)
    b = self.wexpr(e.kids[1], a[0].t)
    flag = self.flag_or(a[1], b[1])
    if a[0].t != "int" or b[0].t != "int" or a[0].v == "undef" or b[0].v == "undef":
        self.overflow_if(flag)
        return (self.arith(e.s, a[0], b[0]), "false")
    x = Val(a[0].v, "int")
    y = Val(b[0].v, "int")
    if e.s in CHECKED:
        r = self.checked(e.s, x.v, y.v)
        return (Val(r[0], "int"), self.flag_or(flag, r[1]))
    if e.s == "<<":
        # as pys_shl: a negative count raises at once; a count of 64 or more leaves 0, inexact
        # unless x is 0
        self.guard(self.scalar_cmp("slt", y, Val("0", "int")), "ValueError: negative shift count")
        big = self.scalar_cmp("ugt", y, Val("63", "int"))
        c = Val(self.scalar("and", [y, Val("63", "int")]), "int")
        sh = Val(self.scalar("shl", [x, c]), "int")
        lost = self.scalar_cmp("ne", Val(self.scalar("ashr", [sh, c]), "int"), x)
        nonzero = self.scalar_cmp("ne", x, Val("0", "int"))
        v = self.select(big, Val("0", "int"), sh)
        return (Val(v, "int"), self.flag_or(flag, self.select(big, Val(nonzero, "bool"), Val(lost, "bool"))))
    return (Val(self.scalar(IOPS[e.s], [x, y]), "int"), flag)
