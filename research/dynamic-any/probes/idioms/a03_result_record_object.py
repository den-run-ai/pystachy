# pystachy: dynamic-any
# #713: the same with dict[str, object], the spelling the Optimization Ladder uses
def run(n: int) -> dict[str, object]:
    total = 0.0
    for i in range(n):
        total += i * 0.5
    return {"n": n, "total": total}


r = run(10)
print(f"n={r['n']} total={r['total']}")
