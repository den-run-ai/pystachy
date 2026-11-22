# pystachy: python-int
# A parameter that a closure takes lives in a cell, which holds a promoting int in a module that
# opts in: the argument enters the cell as one, whether the function rebinds it, a nonlocal
# write grows it past 64 bits, or the argument is already past 64 bits or -2**63.


def make_adder(x):
    def adder(y):
        return x + y
    x = x + 1
    return adder


def make_counter(start):
    def bump(by):
        nonlocal start
        start = start * by
        return start
    return bump


def make_reader(x):
    def read():
        return x
    return read


inc = make_adder(0)
print(inc(1), inc(2 ** 64))
big = make_adder(2 ** 70)
print(big(-1))
low = make_adder(-2 ** 63)
print(low(0), low(-1))
c = make_counter(3)
print(c(2 ** 40), c(2 ** 40), c(-1))
r = make_reader(-2 ** 63)
print(r(), type(r()).__name__)
print(make_reader(5)() + 2 ** 63)
