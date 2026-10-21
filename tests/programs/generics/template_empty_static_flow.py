# An untyped empty list read before the code that fills it takes the type of the first fill that
# runs for the argument types: not one after a return or break that a decided test makes certain,
# in a while loop whose test is false, or in an operand of a conditional expression, and or or
# that the test leaves out. A parameter whose argument is None is None up to a statement that
# can give it another value: not one under a test that is false while it is None, nor x = None.


def after_break(x):
    xs = []
    print(xs)
    for i in range(1):
        if isinstance(x, int):
            break
        xs.append("a")
    xs.append(x)
    return xs


def ifexp(x):
    xs = []
    print(xs)
    xs.append(1) if isinstance(x, int) else xs.append("a")
    return xs


def andop(x):
    xs = []
    print(xs)
    isinstance(x, int) and xs.append(1)
    xs.append("a")
    return xs


def whilefalse(x):
    xs = []
    print(xs)
    while isinstance(x, int) and len(xs) < 1:
        xs.append(1)
    xs.append("a")
    return xs


def guarded(x=None):
    xs = []
    print(xs)
    if x is not None:
        x = x + 1
    if x is None:
        xs.append(1)
    return xs


def other_param(x=None, y=None):
    xs = []
    print(xs)
    if y is not None:
        x = 5
    if isinstance(x, int):
        xs.append("five")
    if x is None:
        xs.append(1)
    return xs


def reset(x=None):
    xs = []
    print(xs)
    x = None
    if x is None:
        xs.append(1)
    else:
        xs.append("s")
    return xs


def dict_guard(x=None):
    d = {}
    print(d)
    if x is not None:
        x = str(x)
    if x is None:
        d["k"] = 1
    return d


print(after_break(1), after_break("q"))
print(ifexp("s"), ifexp(2))
print(andop("s"))
print(whilefalse("s"))
print(guarded())
print(other_param())
print(reset())
print(dict_guard())
