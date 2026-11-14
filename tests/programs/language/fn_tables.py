# Functions of one annotated signature in a list, a dict, tuples in a list, a variable, a
# conditional expression or a function's returns are held as the Callable of that signature;
# a lambda or a bound method among them becomes one too.
import math
from typing import Callable


def add(a: int, b: int) -> int:
    return a + b


def sub(a: int, b: int) -> int:
    return a - b


def mul(a: int, b: int) -> int:
    return a * b


def shout(s: str) -> str:
    return s.upper() + "!"


def whisper(s: str) -> str:
    return s.lower() + "..."


class Calc:
    def __init__(self, base: int) -> None:
        self.base = base

    def plus(self, a: int, b: int) -> int:
        return self.base + a + b


OPS = [add, sub, mul]
TABLE = {"+": add, "-": sub, "*": mul}
PAIRS = [("add", add), ("sub", sub), ("mul", mul)]
VOICES = (shout, whisper)
MIXED = {"add": add, "pow": lambda a, b: a ** b}


def pick(name: str):
    if name == "add":
        return add
    return sub


def choose(flag: bool) -> int:
    op = add
    if flag:
        op = mul
    return op(3, 4)


def run(ops, a: int, b: int) -> list[int]:
    return [op(a, b) for op in ops]


print([op(7, 2) for op in OPS], run(OPS, 9, 3))
print([TABLE[k](8, 2) for k in sorted(TABLE)], TABLE["-"](1, 5))
for name, fn in PAIRS:
    print(name, fn(6, 3), end="; ")
print()
print(VOICES[0]("Hi"), VOICES[1]("Hi"))
print(sorted((k, f(2, 5)) for k, f in MIXED.items()))
print(pick("add")(2, 3), pick("x")(2, 3), choose(True), choose(False))
OPS.append(sub)
TABLE["plus"] = add
print(len(OPS), OPS[-1](1, 1), TABLE["plus"](4, 4))
f = shout if len(OPS) > 3 else whisper
print(f("ok"))
c = Calc(10)
handlers = {"add": add, "calc": c.plus}
print(handlers["calc"](1, 2), handlers["add"](1, 2))
typed: list[Callable[[int, int], int]] = [add]
typed.append(sub)
typed.append(mul)
print(len(typed), typed[1](5, 5), typed[2](5, 5))
steps: list[Callable[[float], int]] = [math.floor, math.ceil]
print([s(2.5) for s in steps])
