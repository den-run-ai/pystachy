"""Mixed-type operand fuzz: one function per program whose result is wanted as a closed union.
The expression is built around a conditional or boolean operand of a binary operator, with
right operands, enclosing or/and and enclosing arithmetic of the same or of another member
type, so that the union the result is wanted as is, or is not, what an operand must be.
usage: gen4.py SEED [python-int|dynamic-any]"""
import random
import sys

NUM = ["int", "float"]


class G:
    def __init__(self, seed: int, mode: str) -> None:
        self.r = random.Random(seed)
        self.mode = mode

    def cond(self) -> str:
        return self.r.choice(["p", "q", "a > 0", "b < a", "x > 0.5", "s != ''", "not p", "a == b", "len(s) > 1", "p and q", "a % 2 == 0"])

    def leaf(self, t: str) -> str:
        r = self.r
        if t == "int":
            return r.choice(["a", "b", "a", "b", "0", "1", "2", "3", "7", "-1", "len(s)"])
        if t == "float":
            return r.choice(["x", "y", "x", "y", "0.0", "1.5", "2.5", "-0.25"])
        if t == "str":
            return r.choice(["s", "t", "s", "t", "''", "'ab'", "'z'"])
        if t == "bool":
            return r.choice(["p", "q", "True", "False", "(a > 0)"])
        if t == "None":
            return "None"
        if t == "any":
            return r.choice(["d", "e"])
        raise ValueError(t)

    def ife(self, t: str, d: int) -> str:
        return f"({self.g(t, d - 1)} if {self.cond()} else {self.g(t, d - 1)})"

    def bop(self, t: str, d: int) -> str:
        return f"({self.g(t, d - 1)} {self.r.choice(['or', 'and'])} {self.g(t, d - 1)})"

    def arith(self, t: str, d: int) -> str:
        r = self.r
        if t == "int":
            k = r.randrange(10)
            if k < 5:
                return f"({self.g('int', d - 1)} {r.choice(['+', '-', '*'])} {self.g('int', d - 1)})"
            if k < 7:
                return f"({self.g('int', d - 1)} {r.choice(['//', '%'])} {self.g('int', d - 1)})"
            if k < 9:
                return f"({self.g('int', d - 1)} {r.choice(['&', '|', '^'])} {self.g('int', d - 1)})"
            return f"({self.g('int', d - 1)} {r.choice(['<<', '>>'])} {r.choice(['1', '3', '(a & 3)'])})"
        if t == "float":
            k = r.randrange(4)
            if k == 0:
                return f"({self.g('int', d - 1)} / {self.g('int', d - 1)})"
            other = r.choice(NUM)
            pair = [self.g("float", d - 1), self.g(other, d - 1)]
            r.shuffle(pair)
            return f"({pair[0]} {r.choice(['+', '-', '*', '/'])} {pair[1]})"
        if t == "str":
            if r.randrange(3) == 0:
                return f"({self.g('str', d - 1)} * {r.choice(['2', '(a & 1)', 'len(t)'])})"
            return f"({self.g('str', d - 1)} + {self.g('str', d - 1)})"
        if t == "bool":
            return f"({self.g('int', d - 1)} {r.choice(['<', '==', '>='])} {self.g('int', d - 1)})"
        return self.leaf(t)

    def g(self, t: str, d: int) -> str:
        # an expression of one type
        if d <= 0 or t in ("None", "any"):
            return self.leaf(t)
        k = self.r.randrange(10)
        if k < 3:
            return self.leaf(t)
        if k < 6:
            return self.ife(t, d)
        if k < 8:
            return self.bop(t, d)
        return self.arith(t, d)

    def held(self, t: str, d: int) -> str:
        # a conditional or boolean expression of one type: what an operand may keep
        k = self.r.randrange(6)
        if k < 3:
            return self.ife(t, d)
        if k < 5:
            return self.bop(t, d)
        return f"({self.ife(t, d)} {self.r.choice(['or', 'and'])} {self.g(t, d - 1)})"

    def mixed(self, members: list[str], d: int) -> str:
        # an expression that may be of any of the members
        r = self.r
        t1 = r.choice(members)
        t2 = r.choice(members)
        k = r.randrange(9 if d > 0 else 3)
        if k < 2:
            return self.g(t1, d)
        if k == 2:
            return "u"
        if k < 5:
            return f"({self.sub(t1, members, d)} if {self.cond()} else {self.sub(t2, members, d)})"
        if k < 8:
            return f"({self.sub(t1, members, d)} {r.choice(['or', 'and'])} {self.sub(t2, members, d)})"
        return f"({self.mixed(members, d - 1)} {r.choice(['+', '-', '*', '/', '//', '%'])} {self.g(r.choice(NUM), d - 1)})"

    def sub(self, t: str, members: list[str], d: int) -> str:
        return self.mixed(members, d - 1) if d > 1 and self.r.randrange(4) == 0 else self.g(t, d - 1)

    def op(self, t: str) -> str:
        r = self.r
        if t == "int":
            return r.choice(["+", "-", "*", "+", "-", "*", "/", "//", "%", "**", "&", "|", "^", "<<", ">>"])
        if t == "float":
            return r.choice(["+", "-", "*", "/", "//", "%", "**"])
        if t == "str":
            return r.choice(["+", "*", "+", "%"])
        return r.choice(["+", "-", "*", "&", "|"])

    def right(self, t: str, op: str, members: list[str], d: int) -> str:
        # a right operand for a left operand of type t
        r = self.r
        if op in ("<<", ">>"):
            return r.choice(["1", "3", "(a & 3)", "(1 if p else 2)"])
        if op == "**":
            return r.choice(["2", "3", "(a & 3)", "(2 if p else 3)", "(-1 if p else 2)", "0.5"])
        if t == "str":
            if op == "*":
                return r.choice(["2", "(a & 1)", "(1 if p else 2)", "len(t)"])
            if op == "%":
                return r.choice(["a", "(a, b)", "s"])
            return self.g("str", d) if r.randrange(4) else self.mixed(members, d)
        k = r.randrange(12)
        if k < 4:
            return self.g(t if t in NUM else "int", d)
        if k < 6:
            return self.g(r.choice(NUM), d)
        if k < 9:
            # a conditional or boolean right operand of two types
            m = [x for x in members if x in NUM] or NUM
            t1 = r.choice(NUM)
            t2 = r.choice(m)
            if r.randrange(2):
                return f"({self.g(t1, d - 1)} if {self.cond()} else {self.g(t2, d - 1)})"
            return f"({self.g(t1, d - 1)} {r.choice(['or', 'and'])} {self.g(t2, d - 1)})"
        if k == 9:
            return "u"
        if k == 10 and self.mode == "dynamic-any":
            return self.leaf("any")
        return self.mixed(members, d)

    def other(self, t: str, members: list[str], d: int) -> str:
        # an operand of an enclosing or/and: mostly of another member type
        r = self.r
        others = [m for m in members if m != t and m != "None"]
        k = r.randrange(6)
        if k < 3 and others:
            return self.g(r.choice(others), d)
        if k == 3:
            return self.mixed(members, d)
        if k == 4 and "None" in members:
            return "None"
        return self.g(t, d)

    def expr(self, members: list[str]) -> str:
        r = self.r
        real = [m for m in members if m != "None"]
        t = r.choice(real)
        d = r.choice([1, 1, 2, 2, 3])
        shape = r.randrange(14)
        o = self.op(t)
        left = self.held(t, d)
        if shape < 3:
            return f"{left} {o} {self.right(t, o, members, d)}"
        if shape == 3:
            # the reviewed shape: an or/and of two types, as an operand
            return f"({self.held(t, d)} {r.choice(['or', 'and'])} {self.other(t, members, d)}) {o} {self.right(t, o, members, d)}"
        if shape == 4:
            return f"({left} {o} {self.right(t, o, members, d)}) {r.choice(['or', 'and'])} {self.other(t, members, d)}"
        if shape == 5:
            o2 = self.op(t)
            return f"({left} {o} {self.right(t, o, members, d)}) {o2} {self.right(t, o2, members, d)}"
        if shape == 6:
            return f"({left} {o} {self.right(t, o, members, d)}) if {self.cond()} else {self.other(t, members, d)}"
        if shape == 7:
            return f"(({self.held('int', d)} * {r.choice(['31', '2654435761', 'b'])} + {self.g('int', d - 1)}) & {r.choice(['255', '0xFFFFFFFF', '(b | 1)'])})"
        if shape == 8:
            return f"({self.held('int', d)} {r.choice(['&', '|', '^'])} {self.right('int', '&', members, d)})"
        if shape == 9:
            return f"-{left}" if t in NUM else f"{left} + {self.g('str', 1)}"
        if shape == 10:
            return f"{self.g(t, d)} {o} {self.held(t, d)}"
        if shape == 11:
            return f"{left} {o} {self.held(t if t != 'bool' else 'int', d)}"
        if shape == 12:
            o2 = self.op(t)
            return f"{left} {o} {self.right(t, o, members, d)} {o2} {self.right(t, o2, members, d)}"
        return self.mixed(members, d)

    def program(self) -> str:
        r = self.r
        unions = [["int", "float"]] * 6 + [["int", "str"]] * 4 + [["float", "str"]] + [["int", "float", "str"]] * 2 + [["int", "float", "None"]] * 2 + [["int", "str", "None"]] + [["bool", "int", "float"]] + [["bool", "str"]]
        members = list(r.choice(unions))
        ut = " | ".join(members)
        e = self.expr(members)
        form = r.randrange(8)
        out = []
        if self.mode != "":
            out.append(f"# pystachy: {self.mode}")
        if self.mode == "dynamic-any":
            out += ["from typing import Any", ""]
        anyp = ", d: Any, e: Any" if self.mode == "dynamic-any" else ""
        out += ["", f"def g(v: {ut}) -> {ut}:", "    return v", "", ""]
        out += [f"def f(a: int, b: int, x: float, y: float, s: str, t: str, p: bool, q: bool, u: {ut}{anyp}) -> {ut}:"]
        if form < 3:
            out += [f"    return {e}"]
        elif form == 3:
            out += [f"    v: {ut} = {e}", "    return v"]
        elif form == 4:
            out += [f"    return g({e})"]
        elif form == 5:
            out += [f"    vs: list[{ut}] = [{e}, u]", "    return vs[0]"]
        elif form == 6:
            out += [f"    dv: dict[str, {ut}] = {{'k': {e}}}", "    return dv['k']"]
        else:
            out += [f"    v: {ut} = u", f"    v = {e}", "    return v"]
        us = {"int": ["3", "0"], "float": ["2.5", "0.0"], "str": ["'q'", "''"], "bool": ["True", "False"], "None": ["None"]}
        uvals = [v for m in members for v in us[m]]
        out += ["", "", "def main() -> None:"]
        rows = []
        ints = [0, 3, -2, 5]
        floats = [0.0, 1.5, -0.5]
        strs = ["", "ab", "z"]
        for i in range(8):
            row = [str(ints[(i + j) % 4]) for j in (0, 1)] + [repr(floats[(i + j) % 3]) for j in (0, 2)] + [repr(strs[(i + j) % 3]) for j in (0, 1)] + [str(i % 2 == 0), str(i % 3 == 0)] + [uvals[i % len(uvals)]]
            if self.mode == "dynamic-any":
                row += [r.choice(["2", "1.5", "'w'", "0"]), r.choice(["3", "0.5", "''"])]
            rows.append(", ".join(row))
        for row in rows:
            out += ["    try:", f"        r = f({row})", "        print(repr(r), type(r).__name__)", "    except Exception as ex:", "        print('raised', type(ex).__name__)"]
        out += ["", "", "main()", ""]
        return "\n".join(out)


if __name__ == "__main__":
    print(G(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "").program())
