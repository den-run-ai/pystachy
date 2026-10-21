# error: cannot infer the type of class attribute 'y'; annotate it (y: T = ...)
N = 3


class C:
    y = N


print(C.y)
