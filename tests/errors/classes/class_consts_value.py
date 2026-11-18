# error: class attribute 'xs' of 'C' used in a class-body default is not supported
class C:
    xs: list[int] = [1]
    ys: list[int] = xs + [2]


print(C.ys)
