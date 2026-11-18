# Displays of classes without a base class in common, without an annotation: a set's items, a
# dict's keys and a list's items are any class's class objects, and type(x) of a union's object
# looks one up, or is isinstance()'s second argument as it is.
class A:
    pass


class B(A):
    pass


class C:
    pass


def same(x: A | C, y: A | C) -> bool:
    return isinstance(x, type(y))


def held(x: A | C, y: A | C) -> bool:
    k: type = type(y)
    return isinstance(x, k)


kinds = {A, C, B}
table = {A: "a", C: "c"}
order = [C, A]
print(sorted(k.__name__ for k in kinds), len(kinds), C in kinds)
print(table[C], table.get(B), [table[k] for k in order])
print(same(B(), A()), same(A(), B()), same(C(), A()), same(C(), C()))
print(held(B(), A()), held(A(), B()), held(C(), A()), held(C(), C()))
