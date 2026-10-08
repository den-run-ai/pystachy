# error: cannot infer the type of 'TREE', an empty dict so far: annotate it (TREE: dict[K, V] = {})
TREE = {}


def put(a: str, b: int, c: str) -> None:
    TREE.setdefault(a, {}).setdefault(b, []).append(c)


put("x", 1, "p")
