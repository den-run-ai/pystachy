# pystachy: dynamic-any
# Lazy local provenance follows the executed branch, including equal rebinding.
from typing import Any


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def selection(flag: bool) -> None:
    x = int("1000")
    y = int("1000")
    selected = x if flag else y
    a: Any = selected
    print("int selection", same(a, x), same(a, y))
    selected = x if not flag else y
    print("opposite", same(a, selected))
    f = float("1000.25")
    g = float("1000.25")
    h = f if flag else g
    b: Any = h
    print("float selection", same(b, f), same(b, g))
    nested = (x if flag else y) if bool(int("1")) else (y if flag else x)
    print("nested", same(a, nested))


def stores(flag: bool) -> None:
    x = int("1000")
    values: list[Any] = [x, (x := int("1000")) if flag else 0]
    print("conditional store", same(values[0], x), same(values[1], x))
    y = float("1000.25")
    floats: list[Any] = [y, (y := float("1000.25")) if flag else 0.0]
    print("float store", same(floats[0], y), same(floats[1], y))
    left = int("1000")
    right = int("1000")
    picks: list[Any] = [left if flag else right, (left := int("1000"))]
    print("selection before store", same(picks[0], left), same(picks[0], right))
    p = int("1000")
    q = int("1000")
    skipped: list[Any] = [p if flag else q, (p := int("1000")) if not flag else 0]
    print("selection before skipped store", same(skipped[0], p), same(skipped[0], q))


def walrus() -> None:
    x = int("1000")
    a: Any = (x := int("1000"))
    print("assigned result", same(a, x))
    y = float("1000.25")
    b: Any = (y := float("1000.25"))
    print("float assigned result", same(b, y))
    # The old value must not become the equal replacement's object.
    values: list[Any] = [(x := int("1000")), (x := int("1000")), x]
    print("successive stores", same(values[0], values[1]), same(values[1], values[2]))
    values = [(x := int("1000")), x]
    print("result then read", same(values[0], values[1]))


selection(True)
selection(False)
stores(True)
stores(False)
walrus()


def local_branch() -> None:
    bx = int("1000")
    bflag = bool(int("0"))
    bys: list[Any] = [bx, (bx := int("2000")) if bflag else 0]
    bw: Any = bx
    print("a read before a store in a branch that does not run", bys[0] is bw, id(bys[0]) == id(bw))


def local_selection() -> None:
    cx = int("1000")
    cz = int("1000")
    cflag = bool(int("1"))
    cw: Any = cx
    cy = cx if cflag else cz
    cv: Any = cy
    print("a value a conditional chooses from two variables", cw is cv, id(cw) == id(cv))


local_branch()
local_selection()


def delayed_same_slot(flag: bool, rebind: bool) -> None:
    x = int("1000")
    seen: Any = x
    y, z = (x if flag else x), (x := int("1000")) if rebind else 0
    a: Any = y
    b: Any = x
    print("same-slot delayed", a is seen, a is b, z)


delayed_same_slot(False, False)
delayed_same_slot(False, True)
delayed_same_slot(True, False)
delayed_same_slot(True, True)


def special_floats(flag: bool, rebind: bool) -> None:
    x = float("nan")
    y = float("nan")
    original: Any = x
    peer: Any = y
    before, after = (x if flag else y), (x := float("nan")) if rebind else y
    a: Any = before
    b: Any = after
    print("NaN selection", same(a, original), same(a, peer), same(b, x), same(original, x))
    negative = -0.0
    positive = 0.0
    chosen = negative if flag else positive
    print("signed zero", same(chosen, negative), same(chosen, positive))


special_floats(False, False)
special_floats(False, True)
special_floats(True, False)
special_floats(True, True)
