# Generates a dynamic-Any program with C classes, each with A fields, all boxed into one list[Any],
# then reads every field through Any. Used to measure dispatcher size and compile time.
import sys
C, A = int(sys.argv[1]), int(sys.argv[2])
out = ["# pystachy: dynamic-any", "from typing import Any", ""]
for c in range(C):
    out.append(f"class K{c}:")
    out.append("    def __init__(self, v: int) -> None:")
    for a in range(A):
        out.append(f"        self.f{a} = v + {a}")
    out.append("")
out.append("xs: list[Any] = []")
for c in range(C):
    out.append(f"xs.append(K{c}({c}))")
out.append("total = 0")
out.append("for x in xs:")
for a in range(A):
    out.append(f"    total += x.f{a}")
out.append("print(total)")
print("\n".join(out))
