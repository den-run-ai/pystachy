# A class object searched in a tuple display of classes, builtin classes too: in, not in, count()
# and index() compare by identity, as == does, whether the tuple names the classes or holds them
class A:
    pass


class B(A):
    pass


def kind(x: int | str) -> str:
    if type(x) in (int, float):
        return "number"
    return "other"


def named(k: type) -> str:
    return str(k in (int, str)) + " " + str(k not in (A, float)) + " " + str((A, int, str).count(k))


k: type = str
print(kind(1), kind("s"))
print(k in (int, str), k in (A, B), (int, float).count(type(2)), (int, float, int).count(int))
print((int, str).index(k), (A, B, int).index(type(B())))
print(named(int), named(A), named(B))
pair = (int, A)
print(type(3) in pair, type(A()) in pair, type(B()) in pair, A in pair)
try:
    print((int, float).index(k))
except ValueError as e:
    print("ValueError", e)
