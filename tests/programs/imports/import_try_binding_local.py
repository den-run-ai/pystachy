# In a function, a name that an import in a try statement of it binds is a local, bound once an
# import of it has run to its end in that call (#196): import fpk.bad, whose code raises, leaves fpk
# unbound, and a later import fpk.good binds it (fpk.bad is then no attribute of fpk). Each call
# starts with the name unbound, also while another call of the function runs. A lambda reads the
# name where it runs, also one made before the import or called after the function returned:
# NameError where it is unbound then (a free variable of the lambda). An import in a function of a
# module the program imports, which is loaded after the module's code, is checked the same way.
from typing import Callable

import good

try:
    import bad
except ValueError as e:
    print("import bad failed:", e)


def boom() -> None:
    raise ValueError("boom")


def rebind() -> str:
    try:
        import fpk.bad
    except ValueError as e:
        print("rebind: import fpk.bad failed:", e)
    import fpk.good

    try:
        print(fpk.bad.X)
    except AttributeError as e:
        print("AttributeError:", e)
    return fpk.good.ok()


def direct() -> int:
    try:
        import bad as b
    except ValueError as e:
        print("direct: import bad failed:", e)
    try:
        return b.Y
    except UnboundLocalError as e:
        print("UnboundLocalError:", e)
    return -1


def lambdas(skip: bool) -> None:
    early = lambda: g.A
    try:
        if skip:
            boom()
        import good as g
    except ValueError:
        print("lambdas: import skipped")
    late = lambda: g.A2() + (lambda: g.K.v)()
    try:
        print(early())
    except NameError as e:
        print("NameError:", e)
    try:
        print(late())
    except NameError as e:
        print("NameError:", e)


def maker(skip: bool) -> Callable[[], int]:
    try:
        if skip:
            boom()
        import good as g2
    except ValueError:
        print("maker: import skipped")
    return lambda: g2.A + 10


def calls(n: int) -> int:
    # (each call's own: the odd ones skip the import, also while an even one's runs)
    try:
        if n % 2 == 1:
            boom()
        import good as g3
    except ValueError:
        pass
    r = calls(n - 1) if n > 0 else 0
    try:
        return r * 10 + [(lambda: g3.A)() for _ in range(1)][0]
    except NameError:
        return r * 10 + 9


print(rebind())
print(direct())
lambdas(False)
lambdas(True)
lambdas(False)
made = maker(False)
unmade = maker(True)
print(made())
try:
    print(unmade())
except NameError as e:
    print("NameError:", e)
print(calls(4))
import user

try:
    print(user.load_bad())
except UnboundLocalError as e:
    print("UnboundLocalError:", e)
print(user.load_good())
