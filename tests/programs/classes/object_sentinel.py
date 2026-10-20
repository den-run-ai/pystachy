# object(): a new object at each call, which the builtins' object class makes, as sentinels are
# made (_MISSING = object()): identity for is, ==, hash() and dict keys, a repr of its address
import mods.objsentinels as objsentinels
from mods.objsentinels import NOTHING, describe

_MISSING = object()
_OTHER = object()


def lookup(d: dict[str, int], k: str, default=_MISSING) -> int:
    # (the sentinel as a default, tested with is: the function never returns it)
    if k in d:
        return d[k]
    if default is _MISSING:
        raise KeyError(k)
    return 0


print(lookup({"a": 1}, "a"), lookup({"a": 1}, "b", None))
try:
    lookup({"a": 1}, "b")
except KeyError as e:
    print("KeyError", e)

a = _MISSING
print(a is _MISSING, a is _OTHER, a is not _OTHER, a == _MISSING, a == _OTHER, a != _OTHER)
print(hash(a) == hash(_MISSING), bool(a), str(a) == repr(a), repr(a) != repr(_OTHER))
r = repr(a)
print(r[:20], r[-1], int(r[18:-1], 16) != 0)
print(f"{a!r}" == r, f"{a}" == r, "%r" % (a,) == r, "%s" % (a,) == r)
print(type(a).__name__, type(a).__qualname__, type(a).__module__, a.__class__.__name__)
print(isinstance(a, object), type(a) is type(_OTHER), type(a) == type(_OTHER))


def fresh():
    return object()


x = fresh()
y = fresh()
print(x is y, x == y, x is x)

# stored and found again: in lists, tuples, dicts (keys and values) and sets
xs = [_MISSING, _OTHER, x]
print(xs.index(_OTHER), _OTHER in xs, y in xs, xs.count(_MISSING))
t = (x, y)
print(t[0] is x, t[1] is y, (x, y) == t)
d = {_MISSING: "missing", _OTHER: "other"}
print(d[_MISSING], d[_OTHER], x in d, len(d))
s = {_MISSING, _MISSING, _OTHER}
print(len(s), _OTHER in s, x in s)
names = {"m": _MISSING}
print(names["m"] is _MISSING)

# another module's sentinel, by import and by attribute: the same object
print(NOTHING is objsentinels.NOTHING, describe(), describe(5), describe(NOTHING))
# a number or bool is never such an object (is: False, is not: True); a str or None is not it either
print(describe(2.5), describe(True), describe("text"), describe(None))
n = 7
f = 2.5
flag = False
print(n is _MISSING, n is not _MISSING, _MISSING is f, flag is not _OTHER)
print(hasattr(a, "x"), getattr(a, "x", "no x"))
