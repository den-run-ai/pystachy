# A small calculator language: tokenizer, recursive-descent parser, tree-walking evaluator.
from __future__ import annotations
from typing import Optional


class Token:
    def __init__(self, kind: str, text: str):
        self.kind = kind
        self.text = text

    def __repr__(self) -> str:
        return f"{self.kind}:{self.text}"


def tokenize(src: str) -> list[Token]:
    toks: list[Token] = []
    i = 0
    while i < len(src):
        c = src[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or c == ".":
            j = i
            while j < len(src) and (src[j].isdigit() or src[j] == "."):
                j += 1
            toks.append(Token("num", src[i:j]))
            i = j
        elif c.isalpha():
            j = i
            while j < len(src) and src[j].isalnum():
                j += 1
            toks.append(Token("name", src[i:j]))
            i = j
        elif c in "+-*/()=^,":
            toks.append(Token("op", c))
            i += 1
        else:
            raise SyntaxError(f"bad character {c!r}")
    toks.append(Token("end", ""))
    return toks


class Expr:
    def __init__(self, kind: str, value: float = 0.0, name: str = "", left: Optional[Expr] = None, right: Optional[Expr] = None):
        self.kind = kind
        self.value = value
        self.name = name
        self.left = left
        self.right = right
        self.args: list[Expr] = []


class Parser:
    def __init__(self, toks: list[Token]):
        self.toks = toks
        self.pos = 0

    def peek(self) -> Token:
        return self.toks[self.pos]

    def take(self) -> Token:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def statement(self) -> Expr:
        if self.peek().kind == "name" and self.toks[self.pos + 1].text == "=":
            name = self.take().text
            self.take()
            return Expr("assign", name=name, left=self.expr())
        return self.expr()

    def expr(self) -> Expr:
        e = self.term()
        while self.peek().text in ("+", "-"):
            op = self.take().text
            e = Expr("bin", name=op, left=e, right=self.term())
        return e

    def term(self) -> Expr:
        e = self.power()
        while self.peek().text in ("*", "/"):
            op = self.take().text
            e = Expr("bin", name=op, left=e, right=self.power())
        return e

    def power(self) -> Expr:
        base = self.unary()
        if self.peek().text == "^":
            self.take()
            return Expr("bin", name="^", left=base, right=self.power())
        return base

    def unary(self) -> Expr:
        if self.peek().text == "-":
            self.take()
            return Expr("neg", left=self.unary())
        return self.atom()

    def atom(self) -> Expr:
        t = self.take()
        if t.kind == "num":
            return Expr("num", value=float(t.text))
        if t.kind == "name":
            if self.peek().text == "(":
                self.take()
                call = Expr("call", name=t.text)
                while self.peek().text != ")":
                    call.args.append(self.expr())
                    if self.peek().text == ",":
                        self.take()
                self.take()
                return call
            return Expr("var", name=t.text)
        if t.text == "(":
            e = self.expr()
            self.take()
            return e
        raise SyntaxError(f"unexpected {t}")


class Interp:
    def __init__(self):
        self.vars: dict[str, float] = {"pi": 3.141592653589793}
        self.calls = 0

    def eval(self, e: Expr) -> float:
        k = e.kind
        if k == "num":
            return e.value
        if k == "var":
            return self.vars[e.name]
        if k == "neg" and e.left is not None:
            return -self.eval(e.left)
        if k == "assign" and e.left is not None:
            v = self.eval(e.left)
            self.vars[e.name] = v
            return v
        if k == "call":
            self.calls += 1
            vals = [self.eval(a) for a in e.args]
            if e.name == "max":
                return max(vals)
            if e.name == "sum":
                return sum(vals)
            if e.name == "sq":
                return vals[0] * vals[0]
            raise NameError(e.name)
        if e.left is None or e.right is None:
            raise ValueError("malformed tree")
        a = self.eval(e.left)
        b = self.eval(e.right)
        if e.name == "+":
            return a + b
        if e.name == "-":
            return a - b
        if e.name == "*":
            return a * b
        if e.name == "/":
            return a / b
        return a ** b


def show(e: Expr) -> str:
    if e.kind == "num":
        return str(e.value)
    if e.kind == "var":
        return e.name
    if e.kind == "call":
        return e.name + "(" + ", ".join([show(a) for a in e.args]) + ")"
    l = show(e.left) if e.left is not None else "?"
    if e.kind == "neg":
        return f"(-{l})"
    if e.kind == "assign":
        return f"{e.name} = {l}"
    r = show(e.right) if e.right is not None else "?"
    return f"({l} {e.name} {r})"


program = """x = 3
y = x * 2 + 1
z = -(x - y) ^ 2 / 4
w = max(x, y, z) + sum(1, 2, 3.5) - sq(2)
area = pi * 2 ^ 2
r = (1 + 2) * (3 + 4) / (5 - 6)"""
it = Interp()
for line in program.split("\n"):
    toks = tokenize(line)
    tree = Parser(toks).statement()
    v = it.eval(tree)
    print(f"{show(tree):<34} => {v:10.4f}   [{len(toks)} tokens]")
print(sorted(it.vars.keys()), it.calls, it.vars["w"])
