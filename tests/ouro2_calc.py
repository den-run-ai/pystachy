from __future__ import annotations


class Expr:
    op: str  # "n" for a number, else an operator
    val: int
    l: Expr
    r: Expr

    def __init__(self, op: str, val: int, l: Expr, r: Expr) -> None:
        self.op = op
        self.val = val
        self.l = l
        self.r = r

    def eval(self) -> int:
        if self.op == "n":
            return self.val
        a = self.l.eval()
        b = self.r.eval()
        if self.op == "+":
            return a + b
        if self.op == "-":
            return a - b
        if self.op == "*":
            return a * b
        return a // b

    def show(self) -> str:
        if self.op == "n":
            return str(self.val)
        return "(" + self.l.show() + " " + self.op + " " + self.r.show() + ")"


class Parser:
    s: str
    i: int

    def __init__(self, s: str) -> None:
        self.s = s
        self.i = 0

    def peek(self) -> str:
        while self.i < len(self.s) and self.s[self.i] == " ":
            self.i += 1
        if self.i < len(self.s):
            return self.s[self.i]
        return ""

    def atom(self) -> Expr:
        c = self.peek()
        if c == "(":
            self.i += 1
            e = self.sum()
            self.peek()
            self.i += 1
            return e
        if c == "-":
            self.i += 1
            return Expr("-", 0, Expr("n", 0, None, None), self.atom())
        n = 0
        while self.i < len(self.s) and ord(self.s[self.i]) >= 48 and ord(self.s[self.i]) <= 57:
            n = n * 10 + ord(self.s[self.i]) - 48
            self.i += 1
        return Expr("n", n, None, None)

    def product(self) -> Expr:
        e = self.atom()
        while self.peek() == "*" or self.peek() == "/":
            op = self.peek()
            self.i += 1
            e = Expr(op, 0, e, self.atom())
        return e

    def sum(self) -> Expr:
        e = self.product()
        while self.peek() == "+" or self.peek() == "-":
            op = self.peek()
            self.i += 1
            e = Expr(op, 0, e, self.product())
        return e


for src in ["1 + 2 * 3", "(1 + 2) * 3", "100 / 7 - -3", "2 * (3 + 4) * (5 - 1)", "-(2 + 3) * 4 / 3", "7"]:
    e = Parser(src).sum()
    print(e.show(), "=", e.eval())
