# A decorator reads its name as CPython evaluates it, before the function's defaults: a name that
# an import in a try statement binds raises NameError there where no import has bound it (#196),
# written as a name (@deco), as a module's attribute (@dm.deco) or as a call (@fac(1),
# @dm.fac(2)); once an import binds it, the decorator runs.
def boom() -> int:
    raise ValueError("boom")


def noisy() -> int:
    print("default evaluated")
    return 0


try:
    boom()
    from decos import deco, fac
except ValueError:
    print("from decos import deco, fac skipped")
try:
    boom()
    import decos as dm
except ValueError:
    print("import decos as dm skipped")


def use_deco() -> None:
    @deco
    def decorated(x: int = noisy()) -> int:
        return x

    print(decorated())


def use_fac() -> None:
    @fac(1)
    def decorated(x: int = noisy()) -> int:
        return x

    print(decorated())


def use_dm() -> None:
    @dm.deco
    def decorated(x: int = noisy()) -> int:
        return x

    print(decorated())


def use_dm_fac() -> None:
    @dm.fac(2)
    def decorated(x: int = noisy()) -> int:
        return x

    print(decorated())


def use_stacked() -> None:
    # (the decorators are evaluated from the top: deco raises before fac(3) runs)
    @deco
    @dm.fac(3)
    def decorated() -> int:
        return 4

    print(decorated())


try:
    use_deco()
except NameError as e:
    print("NameError:", e)
try:
    use_fac()
except NameError as e:
    print("NameError:", e)
try:
    use_dm()
except NameError as e:
    print("NameError:", e)
try:
    use_dm_fac()
except NameError as e:
    print("NameError:", e)
try:
    use_stacked()
except NameError as e:
    print("NameError:", e)

# imports that run bind the names, outside a try statement as in one
from decos import deco, fac

try:
    import decos as dm
except ImportError:
    print("never")
use_deco()
use_fac()
use_dm()
use_dm_fac()
use_stacked()


def local() -> None:
    # a function's own import, its first statement in the try (the read is checked as it runs)
    try:
        from decos import deco as ldeco
    except ImportError:
        print("never")

    @ldeco
    def inner() -> int:
        return 5

    print(inner())


local()
