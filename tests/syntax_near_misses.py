# Code close to CPython's syntax errors that is valid: it compiles where it runs, and where it
# does not run (a template never called, a module's function never called) Pystachy accepts it
# even where it could not compile it.
import os
import mods.near


class P:
    def __init__(self) -> None:
        self.y = 0


def never(x, k):
    [a, *b] = x
    *c, d = x
    for (e, g) in x:
        pass
    with x as (h, i):
        pass
    try:
        pass
    except ValueError:
        pass
    except:
        pass
    j = lambda a, b=1, *c, d, **e: a
    m = [lambda: (yield) for v in x]
    n = x(*k, a)
    o = x(a, **k)
    p = x(**k, a=1)

    def outer() -> None:
        q = 1

        def inner() -> None:
            nonlocal q
            q = 2

    async def co(r):
        await r
        async for s in r:
            pass
        async with r as t:
            pass
        await r.s() ** 2
        return [u async for u in r]

    # names bound only by := in a def's default, annotation or decorator, a lambda's default, a
    # class's base, by a match statement's patterns and guard, and by a type statement
    def g(a=(y := 1), b: (z := int) = 2) -> (u := int):
        return a

    lam = lambda a=(lw := 1): a

    @(dw := lambda f: f)
    def deco() -> None:
        pass

    class B((cb := object)):
        pass

    match x:
        case [ma, *mrest] if (mg := ma):
            pass
        case {"k": mk, **mkw}:
            pass
        case P(y=my) as mp:
            pass

    type TA = int

    def binds() -> None:
        nonlocal y, z, u, lw, dw, cb, ma, mrest, mg, mk, mkw, my, mp, TA

    # := where a named expression may stand; yield where a yield expression may
    wa = [wb := 1, 2]
    wc = x[wd := 0]
    x(we := 1)
    wf = {wg := 1}
    if wh := x:
        pass
    while wi := x:
        break
    ya = yield
    yb = yield 1, 2
    yc = yield from x
    yd = (yield)
    print(f"{yield}")
    da = {**k, "key": 1}
    db = {*x, 1}

    class G((v for v in x)):
        pass

    def tp[*Ts = *tuple[int]]() -> None:
        pass

    return [(v := w) for w in x]


(a) = 1
(b), c = 2, 3
p = P()
p.y = 4
(p.y) = p.y + a
for (d, e) in [(5, 6)]:
    print(a, b, c, d, e, p.y)
with open(os.devnull) as (f):
    print(f.read() == "")
del (a), [b, c]
xs = [1, 2, 3]
del xs[0], (xs[1])
print(xs, f"{d, e}", f"{d, e = }")
# a replacement field may go on over lines, also in a single-quoted f-string, and a comment in it
# runs to the end of its line
print(f"a{d # a comment: } is no end
}b", f"c{d
+ 1}d", f"{'#'}")
print(mods.near.used(7))
