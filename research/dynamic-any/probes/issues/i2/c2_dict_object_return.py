# pystachy: dynamic-any

def run(n: int) -> dict[str, object]:
    return {"n": n, "total": n * 0.5}


print(run(3))
