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
        return [u async for u in r]

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
print(mods.near.used(7))
