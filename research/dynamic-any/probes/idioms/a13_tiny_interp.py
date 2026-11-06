# pystachy: dynamic-any
# a tiny stack-machine interpreter over values of several types
from typing import Any


def run(prog: list[Any]) -> list[Any]:
    stack: list[Any] = []
    for ins in prog:
        if isinstance(ins, str) and ins == "add":
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b)
        elif isinstance(ins, str) and ins == "dup":
            stack.append(stack[-1])
        elif isinstance(ins, str) and ins == "len":
            stack.append(len(stack.pop()))
        else:
            stack.append(ins)
    return stack


print(run([1, 2, "add", "dup", "add"]))
print(run([[1, 2], [3], "add", "len", 2.5, "add"]))
print(run([["x"], ["y"], "add"]))
