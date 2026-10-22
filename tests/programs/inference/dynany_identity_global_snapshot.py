# pystachy: dynamic-any
# A global's object is captured when it is read, before another operand can rebind it.
from typing import Any

import mods.dynidentity_snapshot as typed

G = int("1000")
F = float("1.5")
seen: Any = None


def same(label: str, a: Any, b: Any) -> None:
    print(label, a is b, id(a) == id(b))


def churn() -> None:
    for i in range(30):
        str([str(i), str(i + 1)])


def replace_g(value: str, box: bool) -> int:
    global G, seen
    G = int(value)
    if box:
        seen = G
    churn()
    return 0


def box_g() -> int:
    global seen
    seen = G
    churn()
    return 0


def replace_f(value: str) -> int:
    global F
    F = float(value)
    churn()
    return 0


def run() -> None:
    global G, F
    for boxed in [False, True]:
        G = int("1000")
        old, _ = G, replace_g("1000", boxed)
        same("equal rebind", old, G)
        same("old copy", old, old)
        G = int("1000")
        before: Any = G
        old, _ = G, replace_g("1000", boxed)
        same("boxed old preserved", old, before)
        same("boxed old distinct", old, G)
        G = int("1000")
        left, right, _ = G, G, replace_g("1000", boxed)
        same("two saved reads", left, right)
        same("two saved reads distinct", right, G)
    G = int("2000")
    old, _ = G, replace_g("3000", False)
    print("different values", old, G)
    same("different rebind", old, G)
    G = int("4000")
    old, _ = G, box_g()
    same("callback only boxes", old, G)
    same("callback box alias", old, seen)
    G = int("5000")
    old, G, _ = G, G, replace_g("5000", True)
    same("restore saved binding", old, G)
    same("restored distinct from callback", old, seen)
    G = int("6000")
    values: list[Any] = [G, replace_g("6000", False)]
    same("display snapshot", values[0], G)
    for value in ["1.5", "-0.0", "nan"]:
        F = float(value)
        old_f, _ = F, replace_f(value)
        same("float rebind", old_f, F)
        F = float(value)
        left_f, right_f, _ = F, F, replace_f(value)
        same("float saved aliases", left_f, right_f)
    # Global reads in a module with inference-only Any also need snapshots when its
    # exported numeric bindings are visible to this dynamic module.
    typed.capture()
    same("typed module snapshot", typed.saved, typed.number)
    before_typed: Any = typed.number
    typed.capture()
    same("typed module saved alias", before_typed, typed.saved)
    same("typed module fresh binding", before_typed, typed.number)
    # A syntactic store on an untaken branch does not invalidate a global read.
    G = int("7000")
    flag = bool(int("0"))
    selected: list[Any] = [G, (G := int("8000")) if flag else 0]
    same("untaken global store", selected[0], G)
    # A non-null companion box belongs to the exact value stored in the global:
    # Any round trips preserve it, while explicit numeric conversion makes a new value.
    boxed_int: Any = int("9000")
    G = boxed_int
    same("Any int global round trip", boxed_int, G)
    for value in ["1.5", "-0.0", "nan"]:
        boxed_float: Any = float(value)
        F = boxed_float
        same("Any float global round trip", boxed_float, F)
    G = int("1000")
    F = float(G)
    print("int to float global", G, F)
    same("int to float fresh box", G, F)
    converted_float: Any = F
    G = int(F)
    print("float to int global", F, G)
    same("float to int fresh box", converted_float, G)
    same("converted float retained", converted_float, F)


run()
