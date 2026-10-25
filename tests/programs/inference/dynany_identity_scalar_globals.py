# pystachy: dynamic-any
# Arithmetic can discard global-read identity; copies and published values cannot.
from typing import Any

G = int("1000")
H = int("1000")
F = float("1.5")
J = float("1.5")
seen: Any = None


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def churn() -> None:
    for i in range(20):
        str([str(i), str(i + 1)])


def scalar_reads(n: int) -> int:
    total = 0
    for i in range(n):
        total += G
        total += int(F)
    return total + G * 2


def scalar_global_return(value: float, take_global: bool) -> float:
    if take_global:
        return F
    return value


def self_store() -> int:
    global G
    local = G
    G = local
    return G + 1


def copy_and_rebind() -> int:
    global G, H
    local = G
    H = local
    G = G + 1
    return H + G


def publish_walrus() -> int:
    global H
    return (H := G) + 1


def publish_local_walrus() -> int:
    global H
    total = (local := G) + 1
    H = local
    return total


def conversions() -> int:
    global H, J
    H = int(G)
    J = float(F)
    return H + int(J)


def replace_g() -> int:
    global G, seen
    seen = G
    G = int("2000")
    churn()
    return 0


def advance() -> int:
    global G, F
    G = G + 1
    F = F + 0.25
    return G + int(F)


def run() -> None:
    global G, H, F
    original: Any = G
    H = G
    print("scalar reads", scalar_reads(3))
    same("read keeps prior alias", original, G)
    print("self store", self_store())
    same("self store keeps prior alias", original, G)
    print("copy and rebind", copy_and_rebind())
    same("saved alias across call", original, H)
    same("rebound global distinct", original, G)

    # These sources have no box before the identity-preserving expression publishes them.
    G = int("3000")
    print("global walrus", publish_walrus())
    same("global walrus publishes alias", G, H)
    G = int("4000")
    print("local walrus", publish_local_walrus())
    same("local walrus publishes alias", G, H)
    G = int("5000")
    F = float("-0.0")
    print("conversions", conversions())
    same("int conversion forwards alias", G, H)
    same("float conversion forwards alias", F, J)

    G = int("2000")
    before: Any = G
    print("arithmetic before callback", G + 1)
    old, _ = G, replace_g()
    same("callback saved old alias", old, before)
    same("callback observed old alias", old, seen)
    same("callback replacement distinct", old, G)
    print("arithmetic after callback", G + 1)

    retained: list[Any] = []
    floats: list[Any] = []
    for i in range(3):
        retained.append(G)
        floats.append(F)
        advance()
        churn()
        same("retained int distinct", retained[i], G)
        same("retained float distinct", floats[i], F)
    print("retained values", retained, floats)

    # A scalar function may read a mutable global without making its parameters
    # observable. Either returned object still keeps its original identity.
    F = float("nan")
    original_float: Any = F
    returned_float: Any = scalar_global_return(float("1.5"), True)
    same("returned global alias", original_float, returned_float)
    F = float("nan")
    same("returned global survives replacement", original_float, returned_float)
    same("returned global replacement distinct", returned_float, F)
    same("scalar parameter return alias", F, scalar_global_return(F, False))
    keys: set[Any] = {original_float, returned_float, F}
    print("returned global NaN keys", len(keys))


run()
