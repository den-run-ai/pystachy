# Builtin classes as values: int, str, list and the others are class objects where a value is
# wanted, as an ordinary class is. A location typed type (type[object]) holds any class's class
# object, a builtin class's or one of the program's, and a list, a dict or a set of several
# builtin classes is typed so. A class object has its names and repr(), is compared and hashed
# by identity, is a dict key and a set element, and type(x) of any value gives one.
class A:
    pass


class B(A):
    pass


class P:
    pass


def kind_of(x: int | str | float | None) -> type:
    return type(x)


def describe(k: type) -> str:
    return k.__name__ + "/" + k.__qualname__ + "/" + k.__module__


kinds: list[type] = [int, str, float, bool, list, dict, tuple, set, frozenset, bytes, object, type, A, B, P, type(None)]
for k in kinds:
    print(k, describe(k), k is int, k == str, k is A, k != B, k is object, k is type(None))
print(kind_of(1), kind_of("s"), kind_of(2.5), kind_of(None))
print(type(1) is kinds[0], type("s") is kinds[1], type(True) is kinds[3], type([1]) is kinds[4], type({1: 2}) is kinds[5])
print(type((1, 2)) is kinds[6], type({1}) is kinds[7], type(frozenset([1])) is kinds[8], type(b"x") is kinds[9])
print(type(A()) is kinds[12], type(B()) is kinds[12], type(B()) is kinds[13], type(None) is kinds[15])
names: dict[type, str] = {int: "integer", str: "string", A: "an A", type(None): "nothing"}
for x in kinds[:2] + kinds[12:13] + kinds[15:]:
    print(names[x])
print(names[type(5)], names[type("five")], names[type(A())], names[type(None)])
print(float in names, bool in names, B in names, len(names))
seen: set[type] = {int, str, int, A}
print(len(seen), int in seen, float in seen, A in seen, B in seen, sorted(k.__name__ for k in seen))
print(int in kinds, complex in kinds, kinds.index(float), kinds.count(int))
print(hash(int) == hash(kinds[0]), hash(A) == hash(kinds[12]), hash(int) == hash(str))
print(f"{kinds[0]} {kinds[1]!r} {kinds[12]!s}", str(kinds[2]), repr(kinds[3]))
print(int, str, repr(float), str(list), f"{dict} {bytes!r}", float.__module__, int.__name__, str.__qualname__)
single = {int: 1}
print(single[int], single[type(7)], len({float, float}))
t = type(5)
print(t, t.__name__, t is int, type(t), type(int), type(type(int)).__name__)
pick = int if len(names) > 1 else str
print(pick, pick is int, pick is str)
registry: dict[str, type] = {"i": int, "s": str, "f": float}
for name in sorted(registry):
    print(name, registry[name], registry[name].__name__, registry[name] is int)
