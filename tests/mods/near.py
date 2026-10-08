# A module whose functions, and a class, use valid code close to CPython's syntax errors that
# Pystachy cannot compile; the program calls only used().


def used(n: int) -> int:
    (m) = n * 6
    return m


def never(x, k):
    [a, *b] = x
    try:
        pass
    except:
        pass
    j = lambda a, b=1: a
    n = x(*k, a)
    o = x(a, **k)

    def outer():
        q = 1

        def inner():
            nonlocal q

    async def co(r):
        await r


class Never:
    def m(self, x: int) -> None:
        y = [lambda: (yield) for v in range(x)]
        z = self.m(*[x])
