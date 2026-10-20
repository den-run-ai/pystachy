# A parsy-style chain of closures (#193) over class templates: Result's value has no annotation,
# so each value type is a specialization of it, and Parser's function is a typed Callable whose
# return names the template. A closure that returns a Result[str] is a
# Callable[[str, int], Result[str]] there, so the parsers of one value type share one layout,
# whatever closure each holds
from typing import Callable


class Result:
    def __init__(self, ok: bool, index: int, value):
        self.ok = ok
        self.index = index
        self.value = value


class Parser:
    def __init__(self, fn: Callable[[str, int], Result], name: str):
        self.fn = fn
        self.name = name

    def __call__(self, s: str, i: int):
        return self.fn(s, i)

    def parse(self, s: str):
        r = self(s, 0)
        return r.value if r.ok and r.index == len(s) else None

    def then(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            o = other(s, r.index)
            return Result(r.ok and o.ok, o.index if r.ok else i, o.value)

        return Parser(run, self.name + " " + other.name)

    def skip(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            o = other(s, r.index)
            return Result(r.ok and o.ok, o.index if r.ok else i, r.value)

        return Parser(run, self.name + " " + other.name)

    def alt(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            return r if r.ok else other(s, i)

        return Parser(run, self.name + " | " + other.name)

    def map(self, f):
        def run(s: str, i: int):
            r = self(s, i)
            return Result(r.ok, r.index, f(r.value))

        return Parser(run, self.name)

    def many(self):
        def run(s: str, i: int):
            values = [self(s, i).value]
            values.clear()
            while True:
                r = self(s, i)
                if not r.ok:
                    return Result(True, i, values)
                values.append(r.value)
                i = r.index

        return Parser(run, self.name + "*")


def char(c: str) -> Parser:
    def run(s: str, i: int):
        if i < len(s) and s[i] == c:
            return Result(True, i + 1, c)
        return Result(False, i, "")

    return Parser(run, repr(c))


def digits() -> Parser:
    def run(s: str, i: int):
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        return Result(j > i, j, s[i:j])

    return Parser(run, "digits")


number = digits().map(len)
sign = char("-").alt(char("+"))
pair = char("(").then(digits()).skip(char(",")).then(digits().map(len)).skip(char(")"))
letters = char("a").alt(char("b")).many()
print(number.parse("12345"), number.parse("12a"), sign.parse("+"), sign.parse("x"))
print(pair.parse("(12,345)"), pair.parse("(12;3)"), letters.parse("abba"), letters.parse(""))
print(number.name, sign.name, pair.name, letters.name)


def double(n: int) -> int:
    return n * 2


def scaled(c: str) -> Parser:
    def run(s: str, i: int):
        # (an ordinary Callable in the function a Parser holds: its adapter is made while the
        # Parser's is compiled)
        f: Callable[[int], int] = double
        ok = i < len(s) and s[i] == c
        return Result(ok, i + 1 if ok else i, f(i))

    return Parser(run, "scaled " + c)


print(scaled("x").parse("x"), char("x").then(scaled("y")).parse("xy"), scaled("z").parse("y"))
