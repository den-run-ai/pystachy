# Seeded differential fuzz of binary operators, comparisons, membership and builtins on Any values.
# Writes a dynamic-Any program; run it under CPython and Pystachy and diff the outputs.
import random
import sys

seed, n = int(sys.argv[1]), int(sys.argv[2])
rnd = random.Random(seed)
vals = ["0", "1", "-1", "2", "7", "-3", "255", "256", "257", "1000", "-1000", "9223372036854775807", "-9223372036854775808",
        "0.0", "-0.0", "1.5", "-2.25", "1e300", "float('inf')", "float('nan')", "True", "False", "None",
        "''", "'a'", "'ab'", "'b'", "'10'", "[]", "[1]", "[1, 'a']", "(1,)", "()", "(1, 2.5)", "{}", "{'k': 1}", "{1: 'x'}"]
ops = ["+", "-", "*", "/", "//", "%", "**", "<<", ">>", "&", "|", "^", "==", "!=", "<", "<=", ">", ">=", "in", "not in", "is"]
un = ["-{}", "+{}", "~{}", "not {}", "bool({})", "len({})", "hash({})", "str({})", "repr({})", "int({})", "float({})"]
out = ["# pystachy: dynamic-any", "from typing import Any", ""]
names = []
for i, v in enumerate(vals):
    out.append(f"v{i}: Any = {v}")
    names.append(f"v{i}")
out.append("")
out.append("def show(tag: str, f: Any) -> None:")
out.append("    print(tag, f)")
out.append("")
cases = []
for k in range(n):
    if rnd.random() < 0.8:
        a, b = rnd.choice(names), rnd.choice(names)
        op = rnd.choice(ops)
        expr = f"{a} {op} {b}"
    else:
        a = rnd.choice(names)
        expr = rnd.choice(un).format(a)
    cases.append(expr)
for k, expr in enumerate(cases):
    out.append("try:")
    out.append(f"    r{k}: Any = {expr}")
    out.append(f"    print({k}, repr(r{k}))")
    out.append("except Exception as e:")
    out.append(f"    print({k}, type(e).__name__, e)")
print("\n".join(out))
