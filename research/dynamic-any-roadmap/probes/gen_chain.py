# A dynamic-Any program with C classes that all have field f0; reads x.f0 through Any N times
# (N from argv) on objects of class K{which}: first (0) or last (C-1) in the dispatcher's chain.
import sys
C, which = int(sys.argv[1]), sys.argv[2]
k = 0 if which == "first" else C - 1
out = ["# pystachy: dynamic-any", "import sys", "from typing import Any", ""]
for c in range(C):
    out += [f"class K{c}:", "    def __init__(self, v: int) -> None:", "        self.f0 = v", ""]
out += ["xs: list[Any] = []"]
for c in range(C):
    out.append(f"xs.append(K{c}({c % 7}))")
out += [f"obj: Any = xs[{k}]", "n = int(sys.argv[1])", "total = 0", "for i in range(n):", "    total += obj.f0", "print(total)"]
print("\n".join(out))
