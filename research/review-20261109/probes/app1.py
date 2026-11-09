"""Expression interpreter: classes, inheritance, dicts, exceptions, recursion."""
from dataclasses import dataclass, field


class ParseError(Exception):
    def __init__(self, msg: str, pos: int) -> None:
        super().__init__(f"{msg} at {pos}")
        self.pos = pos


class Token:
    def __init__(self, kind: str, text: str, pos: int) -> None:
        self.kind = kind
        self.text = text
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.text!r}, {self.pos})"


def tokenize(src: str) -> list[Token]:
    out: list[Token] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            seen_dot = False
            while j < n and (src[j].isdigit() or (src[j] == "." and not seen_dot)):
                if src[j] == ".":
                    seen_dot = True
                j += 1
            out.append(Token("num", src[i:j], i))
            i = j
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            out.append(Token("name", src[i:j], i))
            i = j
        elif src.startswith("**", i) or src.startswith("//", i) or src.startswith("<=", i) or src.startswith(">=", i) or src.startswith("==", i) or src.startswith("!=", i):
            out.append(Token("op", src[i : i + 2], i))
            i += 2
        elif c in "+-*/%()<>=,?:":
            out.append(Token("op", c, i))
            i += 1
        else:
            raise ParseError(f"bad character {c!r}", i)
    out.append(Token("end", "", n))
    return out


class Node:
    def eval(self, env: dict[str, float]) -> float:
        raise NotImplementedError

    def show(self) -> str:
        return "?"


class Num(Node):
    def __init__(self, v: float) -> None:
        self.v = v

    def eval(self, env: dict[str, float]) -> float:
        return self.v

    def show(self) -> str:
        return repr(self.v)


class Var(Node):
    def __init__(self, name: str) -> None:
        self.name = name

    def eval(self, env: dict[str, float]) -> float:
        try:
            return env[self.name]
        except KeyError as e:
            raise NameError(f"undefined: {self.name}") from e

    def show(self) -> str:
        return self.name


class Bin(Node):
    def __init__(self, op: str, a: Node, b: Node) -> None:
        self.op = op
        self.a = a
        self.b = b

    def eval(self, env: dict[str, float]) -> float:
        x = self.a.eval(env)
        y = self.b.eval(env)
        op = self.op
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return x / y
        if op == "//":
            return x // y
        if op == "%":
            return x % y
        if op == "**":
            return x**y
        if op == "<":
            return float(x < y)
        if op == ">":
            return float(x > y)
        if op == "<=":
            return float(x <= y)
        if op == ">=":
            return float(x >= y)
        if op == "==":
            return float(x == y)
        if op == "!=":
            return float(x != y)
        raise ValueError(op)

    def show(self) -> str:
        return f"({self.a.show()} {self.op} {self.b.show()})"


class Neg(Node):
    def __init__(self, a: Node) -> None:
        self.a = a

    def eval(self, env: dict[str, float]) -> float:
        return -self.a.eval(env)

    def show(self) -> str:
        return f"-{self.a.show()}"


class Cond(Node):
    def __init__(self, c: Node, a: Node, b: Node) -> None:
        self.c = c
        self.a = a
        self.b = b

    def eval(self, env: dict[str, float]) -> float:
        return self.a.eval(env) if self.c.eval(env) else self.b.eval(env)

    def show(self) -> str:
        return f"({self.c.show()} ? {self.a.show()} : {self.b.show()})"


class Call(Node):
    def __init__(self, name: str, args: list[Node]) -> None:
        self.name = name
        self.args = args

    def eval(self, env: dict[str, float]) -> float:
        vals = [a.eval(env) for a in self.args]
        if self.name == "max":
            return max(vals)
        if self.name == "min":
            return min(vals)
        if self.name == "sum":
            return sum(vals)
        if self.name == "abs" and len(vals) == 1:
            return abs(vals[0])
        raise TypeError(f"bad call {self.name}/{len(vals)}")

    def show(self) -> str:
        return f"{self.name}({', '.join(a.show() for a in self.args)})"


PREC: dict[str, int] = {"?": 1, "==": 2, "!=": 2, "<": 3, ">": 3, "<=": 3, ">=": 3, "+": 4, "-": 4, "*": 5, "/": 5, "//": 5, "%": 5, "**": 7}


class Parser:
    def __init__(self, toks: list[Token]) -> None:
        self.toks = toks
        self.i = 0

    def peek(self) -> Token:
        return self.toks[self.i]

    def next(self) -> Token:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, text: str) -> None:
        t = self.next()
        if t.text != text:
            raise ParseError(f"expected {text!r}, got {t.text!r}", t.pos)

    def primary(self) -> Node:
        t = self.next()
        if t.kind == "num":
            return Num(float(t.text))
        if t.kind == "name":
            if self.peek().text == "(":
                self.next()
                args: list[Node] = []
                if self.peek().text != ")":
                    args.append(self.expr(0))
                    while self.peek().text == ",":
                        self.next()
                        args.append(self.expr(0))
                self.expect(")")
                return Call(t.text, args)
            return Var(t.text)
        if t.text == "(":
            e = self.expr(0)
            self.expect(")")
            return e
        if t.text == "-":
            return Neg(self.expr(6))
        raise ParseError(f"unexpected {t.text!r}", t.pos)

    def expr(self, minprec: int) -> Node:
        left = self.primary()
        while True:
            t = self.peek()
            p = PREC.get(t.text, -1) if t.kind == "op" else -1
            if p < minprec or p < 0:
                return left
            self.next()
            if t.text == "?":
                a = self.expr(0)
                self.expect(":")
                b = self.expr(1)
                left = Cond(left, a, b)
            elif t.text == "**":
                left = Bin(t.text, left, self.expr(p))
            else:
                left = Bin(t.text, left, self.expr(p + 1))


@dataclass
class Result:
    src: str
    ok: bool = True
    value: float = 0.0
    error: str = ""
    shown: str = ""
    steps: list[str] = field(default_factory=list)


def evaluate(src: str, env: dict[str, float]) -> Result:
    r = Result(src)
    try:
        toks = tokenize(src)
        r.steps.append(f"{len(toks)} tokens")
        p = Parser(toks)
        tree = p.expr(0)
        if p.peek().kind != "end":
            raise ParseError("trailing input", p.peek().pos)
        r.shown = tree.show()
        r.steps.append("parsed")
        r.value = tree.eval(env)
        r.steps.append("evaluated")
    except ParseError as e:
        r.ok = False
        r.error = f"ParseError: {e} (pos={e.pos})"
    except (ZeroDivisionError, OverflowError) as e:
        r.ok = False
        r.error = f"{type(e).__name__}: {e}"
    except NameError as e:
        r.ok = False
        r.error = f"NameError: {e}; cause={type(e.__cause__).__name__}"
    except Exception as e:
        r.ok = False
        r.error = f"other {type(e).__name__}: {e}"
    finally:
        r.steps.append("done")
    return r


def main() -> None:
    env = {"x": 3.0, "y": -2.5, "pi": 3.141592653589793, "big": 1e308}
    srcs = [
        "1 + 2 * 3", "(1 + 2) * 3", "2 ** 3 ** 2", "-2 ** 2", "x * y - pi", "7 // 2 + 7 % 2", "-7 // 2", "-7 % 2", "7.5 % -2",
        "1 / 0", "1 // 0", "1 % 0", "big * 10", "big ** 2", "0 ** -1", "(-8) ** 0.5" if False else "8 ** 0.5", "x < y ? 1 : 2", "x > y ? x == 3 ? 10 : 20 : 30",
        "max(1, x, y)", "min(x, y) + sum(1, 2, 3)", "abs(y)", "abs(1, 2)", "foo(1)", "z + 1", "1 +", "(1 + 2", "1 $ 2", "1 2", "", ".5 + 1.", "1.2.3",
        "sum()", "max()", "1e3", "x ** 1000", "2 ** 0.5 ** 2", "1 - - 1", "1 == 1.0", "0.1 + 0.2 == 0.3", "0.1 + 0.2 != 0.3", "1 <= 1 >= 0",
    ]
    for s in srcs:
        r = evaluate(s, env)
        if r.ok:
            print(f"{s!r:32} = {r.value!r:24} {r.shown} {r.steps}")
        else:
            print(f"{s!r:32} ! {r.error} {r.steps}")
    print(Result("a") == Result("a"), Result("a") == Result("b"), Result("a", steps=["x"]))


main()
