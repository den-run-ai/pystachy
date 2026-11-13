# isinstance() and issubclass() with class objects that may be builtin classes': a value is an
# instance of its own class's, of its bases' and of object's, a bool of int's too, and None of
# NoneType's. issubclass() takes a class named, a class object or a tuple of them.
class A:
    pass


class B(A):
    pass


class P:
    pass


def check(label: str, x: int | str | float | bool | None, kinds: list[type]) -> None:
    print(label, [isinstance(x, k) for k in kinds])


def check_object(label: str, x: A | P | None, kinds: list[type]) -> None:
    print(label, [isinstance(x, k) for k in kinds])


def subs(k: type, kinds: list[type]) -> None:
    print(k.__name__, [issubclass(k, j) for j in kinds], issubclass(k, int), issubclass(k, object), issubclass(k, A), issubclass(k, (int, str)), issubclass(k, (A, P)))


kinds: list[type] = [int, str, float, bool, object, A, B, P, type(None), list]
check("int", 3, kinds)
check("bool", True, kinds)
check("str", "s", kinds)
check("float", 1.5, kinds)
check_object("A", A(), kinds)
check_object("B", B(), kinds)
check_object("P", P(), kinds)
check_object("no object", None, kinds)
check("None", None, kinds)
for k in kinds:
    subs(k, kinds)
n = 5
items = [1, 2]
table = {"a": 1}
pair = (1, "x")
print([isinstance(n, k) for k in kinds], [isinstance(items, k) for k in kinds])
containers: list[type] = [dict, tuple, object, list, int]
print([isinstance(table, k) for k in containers], [isinstance(pair, k) for k in containers])
print(isinstance(n, type(n)), isinstance("s", type(n)), isinstance(True, type(n)), isinstance(n, type(True)))
print(issubclass(bool, kinds[0]), issubclass(int, kinds[3]), issubclass(str, kinds[4]), issubclass(float, (kinds[0], kinds[2])))
