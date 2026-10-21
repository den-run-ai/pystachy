# K classes whose __eq__ (unannotated other) does not compile for an Any operand (a typed list
# compared with an Any value's field), each boxed into Any: the compiler declines them one pass at
# a time (Gen.xnot). Also F filler functions, to make each whole-program pass cost something.
import sys
K, F = int(sys.argv[1]), int(sys.argv[2])
out = ["# pystachy: dynamic-any", "from typing import Any", ""]
for k in range(K):
    out += [f"class B{k}:", "    def __init__(self, n: int) -> None:", "        self.items: list[int] = [n]", "",
            "    def __eq__(self, other) -> bool:", "        return self.items == other.items", ""]
for f in range(F):
    out += [f"def filler{f}(x: int) -> int:", "    s = 0", "    for i in range(x):", f"        s += i * {f + 1}", "    return s", ""]
out += ["xs: list[Any] = []"]
for k in range(K):
    out.append(f"xs.append(B{k}(1))")
out += ["print(xs[0] == xs[0], len(xs))"]
for f in range(F):
    out.append(f"print(filler{f}(3))")
print("\n".join(out))
