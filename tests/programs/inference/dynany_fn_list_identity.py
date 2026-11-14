# pystachy: dynamic-any
# A list, a dict or tuples in a list of different functions in a module that compiles Any
# dynamically hold the function objects themselves, with their identity and type: none becomes
# a container of Callable values, which have neither (as each is in a module that does not
# opt in).
from typing import Any


def double(x: Any) -> Any:
    return x * 2


def negate(x: Any) -> Any:
    return -x


table = [double, negate]
for f in table:
    print(f(3), f is double, f == negate, f is not negate, type(f).__name__, callable(f))
for g in [negate, double]:
    print(g(4), g is negate, type(g) is type(double))
by_name = {"d": double, "n": negate}
print(by_name["d"](5), by_name["n"] is negate, type(by_name["d"]).__name__)
pairs = [("d", double), ("n", negate)]
print([(k, f(6), f is double, type(f).__name__) for k, f in pairs])
