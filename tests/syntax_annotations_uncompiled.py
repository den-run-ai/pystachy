# CPython's compiler never compiles a variable annotation in a function body, so what it rejects
# in compiled code (await outside an async def, an async comprehension, := of __debug__) is
# valid there; x.__debug__ += 1 binds no name __debug__
def f(y):
    x: (await y) = 1
    z: [v async for v in y] = []
    w: (lambda: (await y)) = 1
    t: (__debug__ := 1) = 1
    y.a: (await y) = 1
    u: (await y)
    y.__debug__ += 1
    y[0].__debug__ //= 2
    return x, z, w, t


def g[T](x: T) -> T:
    def h():
        T = 1

        def k():
            nonlocal T
            return T
        return k
    return x


def g2[T](x):
    class C:
        T = 1

        def m(self):
            def k():
                nonlocal T
            return k
    return C


print("ran")
