# pystachy: dynamic-any
# An int or float variable of typed code holds one object, as CPython's name does (#797, #807's
# review): each time it becomes an Any value, it gives that object. A typed variable that is
# assigned an Any value holds the Any value's object, a copy of a variable holds its object, and
# an int literal stored in one is the module's constant. A value computed at run time is a new
# object, also where it is equal to another.
from typing import Any, Iterator

import mods.dyntyped_vars as tv


def both(label: str, a: Any, b: Any) -> None:
    # (both are alive here, held by the arguments, as CPython's ids are compared only then)
    print(label, a is b, a is not b, id(a) == id(b))


def ident(a: Any) -> int:
    return id(a)


def churn() -> int:
    # (allocations, which collect under GC stress: a box that only its variable holds survives)
    t = 0
    for i in range(300):
        t += len([str(i), str(i + 1)])
    return t


def param(n: int, x: float) -> None:
    a: Any = n
    b: Any = n
    both("an int parameter, twice", a, b)
    f: Any = x
    g: Any = x
    both("a float parameter, twice", f, g)


def gen() -> Iterator[bool]:
    # (its variables live in its frame between its resumptions, their box slots too)
    n: int = int("9000")
    a: Any = n
    yield True
    churn()
    b: Any = n
    yield a is b and id(a) == id(b)


G: int = int("1000")
H: float = float("2.5")
G2: int = int("8000")
K = 5000


def module_vars() -> None:
    a: Any = G
    b: Any = G
    both("an int module variable, twice", a, b)
    f: Any = H
    g: Any = H
    both("a float module variable, twice", f, g)
    k: Any = K
    both("a module constant, its literal", k, 5000)
    i = ident(G2)  # (its first crossing: only G2 holds the object)
    churn()
    print("an int module variable's id, after allocations", i == ident(G2))


def other_module() -> None:
    # (a module that does not compile Any as dynamic values: tests/mods/dyntyped_vars.py)
    a: Any = tv.N
    b: Any = tv.N
    both("another module's int variable, twice", a, b)
    f: Any = tv.F
    g: Any = tv.F
    both("another module's float variable, twice", f, g)


def run() -> None:
    n: int = int("1000")
    a: Any = n
    b: Any = n
    both("an int variable, twice", a, b)
    x: float = float("1.5")
    f: Any = x
    g: Any = x
    both("a float variable, twice", f, g)
    d: Any = int("2000")
    m: int = d
    e: Any = m
    both("Any, int, Any", d, e)
    p: Any = float("3.5")
    y: float = p
    q: Any = y
    both("Any, float, Any", p, q)
    pf: Any = float("5.5")
    qf = pf
    if isinstance(pf, float):
        both("an Any float that isinstance() narrows", pf, qf)
        yf: float = pf
        rf: Any = yf
        both("narrowed to float, float, Any", qf, rf)
    pn: Any = int("5000")
    qn = pn
    if isinstance(pn, int):
        both("an Any int that isinstance() narrows", pn, qn)
        zn: int = pn
        rn: Any = zn
        both("narrowed to int, int, Any", qn, rn)
    k = n
    s: Any = k
    both("a copy of a variable that became Any", a, s)
    lit: int = 1000
    t: Any = lit
    both("a literal in an int variable, the literal", t, 1000)
    n2: int = int("1000")
    u: Any = n2
    both("two int variables of one value", a, u)
    z: int = int("6000")
    i = ident(z)  # (its first crossing: only z holds the object)
    churn()
    print("an int variable's id, after allocations", i == ident(z))
    zf: float = float("6.5")
    j = ident(zf)
    churn()
    print("a float variable's id, after allocations", j == ident(zf))
    last: Any = None
    for r in range(3):
        w: int = int("3000")
        cur: Any = w
        again: Any = w
        print("a loop's value", r, cur is again, cur is last)
        last = cur
    n = n + 0
    v: Any = n
    both("an int variable, a sum assigned to it", a, v)


M: int = int("7000")
ma: Any = M
mb: Any = M
both("an int module variable at module level, twice", ma, mb)
run()
param(int("4000"), float("4.5"))
module_vars()
other_module()
print("a generator's int variable, across a yield", list(gen()))
