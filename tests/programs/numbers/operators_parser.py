# Parser objects combined with |, >> and << as parsy combines them (alt, then and skip), whose
# operator methods take the other parser without an annotation: each method is a template,
# compiled for the parser it is given (an operator's method may be one, see template_ok), and
# Parser is a class template whose function is a typed Callable, one specialization per value
# type
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

    def __or__(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            return r if r.ok else other(s, i)

        return Parser(run, "(" + self.name + " | " + other.name + ")")

    def __rshift__(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            o = other(s, r.index)
            return Result(r.ok and o.ok, o.index if r.ok else i, o.value)

        return Parser(run, "(" + self.name + " >> " + other.name + ")")

    def __lshift__(self, other):
        def run(s: str, i: int):
            r = self(s, i)
            o = other(s, r.index)
            return Result(r.ok and o.ok, o.index if r.ok else i, r.value)

        return Parser(run, "(" + self.name + " << " + other.name + ")")

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


def num(s: str) -> int:
    return int(s) if s != "" else -1


number = digits().map(num)
sign = char("-") | char("+")
# >> and << bind tighter than |, and group from the left: ((sign >> number) << char(";")) | ...
signed = sign >> number << char(";") | char("=") >> number
pair = char("(") >> digits() << char(",") >> number << char(")")
letters = (char("a") | char("b") | char("c")).many()
print(signed.parse("-12;"), signed.parse("=7"), signed.parse("+3"), signed.parse("*1;"))
print(pair.parse("(12,345)"), pair.parse("(12;3)"), letters.parse("abcab"), letters.parse("abd"))
print(signed.name)
print(pair.name, letters.name)

# |= is __or__ (Parser has no __ior__): another parser of the same type, which the name holds
vowel = char("a")
for v in "eiou":
    vowel |= char(v)
print(vowel.name, [vowel.parse(c) for c in "aeixu"])
