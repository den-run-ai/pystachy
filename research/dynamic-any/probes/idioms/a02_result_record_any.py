# pystachy: dynamic-any
# #713: a benchmark function returning a heterogeneous result record
from typing import Any


def run(n: int) -> dict[str, Any]:
    total = 0.0
    for i in range(n):
        total += i * 0.5
    return {"n": n, "total": round(total, 3)}


r = run(10)
print(f"n={r['n']} total={r['total']}")
