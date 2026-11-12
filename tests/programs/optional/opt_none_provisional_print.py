# reads of a local that holds None so far, in loops whose later passes give it a value: each
# is compiled again once a store types it, and prints what CPython prints
def f() -> None:
    x = None
    for i in range(3):
        print(x, str(x), repr(x), f"{x}", [x] == [None])
        y = "a" + str(i)
        x = y


def g(flag: bool) -> None:
    x = None
    n = 0
    while n < 3:
        print("g", x)
        if flag:
            z = n * 2
            x = z
        n += 1


def h() -> None:
    x = None
    for i in range(2):
        print("h", x)
        ys = [i]
        x = ys


f()
g(True)
g(False)
h()
