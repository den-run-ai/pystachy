# functools.wraps() and update_wrapper() (lib/functools.py, CPython's), which the compiler applies:
# a wrapper's __name__ and __qualname__ are the wrapped function's, of a module's function, a
# closure, a lambda, a builtin, a bound method and a wrapper itself (stacked decorators), with
# assigned naming either (a tuple, a list, a module's tuple, functools.WRAPPER_ASSIGNMENTS); a
# callable object, which has none, leaves the wrapper's own; and the wrapper keeps working as itself
import functools
from functools import WRAPPER_ASSIGNMENTS, WRAPPER_UPDATES, update_wrapper, wraps


def logged(f):
    @wraps(f)
    def wrapper(*args):
        print("call", f.__name__)
        return f(*args)
    return wrapper


def timed(f):
    @functools.wraps(f)
    def timer(*args):
        return f(*args)
    return timer


@logged
def add(a: int, b: int) -> int:
    return a + b


@timed
@logged
def mul(a: int, b: int) -> int:
    return a * b


def name_only(f):
    @wraps(f, assigned=("__name__",))
    def inner(x):
        return f(f(x))
    return inner


def qual_only(f):
    @wraps(f, ("__qualname__", "__doc__"))
    def inner(x):
        return f(x)
    return inner


def neither(f):
    @wraps(f, assigned=(), updated=())
    def inner(x):
        return f(x)
    return inner


ONLY_MODULE = ("__module__",)


def module_only(f):
    @wraps(f, ONLY_MODULE)
    def kept(x):
        return f(x)
    return kept


def attr_form(f):
    @functools.wraps(f, functools.WRAPPER_ASSIGNMENTS, functools.WRAPPER_UPDATES)
    def named(x):
        return f(x)
    return named


def plain(f):
    def g(x):
        return f(x)
    return update_wrapper(g, f)


def plain_default(f):
    def g(x):
        return f(x)
    update_wrapper(g, f, WRAPPER_ASSIGNMENTS, WRAPPER_UPDATES)
    return g


def inc(x: int) -> int:
    return x + 1


def outer():
    def nested(x: int) -> int:
        return x * 3
    return logged(nested)


class Box:
    def method(self, x: int) -> int:
        return x - 1


class Callme:
    def __call__(self, x: int) -> int:
        return x + 10


print(add(2, 3), add.__name__, add.__qualname__)
print(mul(3, 4), mul.__name__, mul.__qualname__)
g1 = name_only(inc)
g2 = qual_only(inc)
g3 = neither(inc)
print(g1(1), g1.__name__, g1.__qualname__, g2(1), g2.__name__, g2.__qualname__, g3(1), g3.__name__, g3.__qualname__)
g4 = module_only(inc)
g5 = attr_form(inc)
print(g4(1), g4.__name__, g4.__qualname__, g5(1), g5.__name__, g5.__qualname__)
h1 = plain(inc)
h2 = plain_default(inc)
print(h1(4), h1.__name__, h1.__qualname__, h2(4), h2.__name__, h2.__qualname__)
n = outer()
print(n(2), n.__name__, n.__qualname__)
b = logged(Box().method)
print(b(5), b.__name__, b.__qualname__)
s = logged(len)
print(s("abc"), s.__name__, s.__qualname__)
lam = logged(lambda x: x * 2)
print(lam(3), lam.__name__, lam.__qualname__)
c = timed(Callme())
print(c(1), c.__name__, c.__qualname__)
print(WRAPPER_ASSIGNMENTS, WRAPPER_UPDATES)
