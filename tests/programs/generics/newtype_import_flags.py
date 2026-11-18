# A NewType that a function imports is a local bound only where the import runs: a call that may
# come first raises UnboundLocalError, a lambda's NameError, as CPython's do
def meters(flag: bool) -> int:
    if flag:
        from mods.newtypes import Meters
    return Meters(3)


def later(flag: bool) -> int:
    if flag:
        from mods.newtypes import Meters
    get = lambda: Meters(5)
    return get()


def guarded() -> int:
    try:
        from mods.newtypes import Meters as M
    except ImportError:
        return -1
    return M(4)


print(meters(True), later(True), guarded())
try:
    print(meters(False))
except UnboundLocalError as e:
    print("UnboundLocalError:", e)
try:
    print(later(False))
except NameError as e:
    print("NameError:", e)
