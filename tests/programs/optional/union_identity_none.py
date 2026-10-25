# is and is not of closed unions of native references compare the objects, None included: a class
# union's None is a null pointer, as a class type's is, whose union tag must not be read (it
# crashed), and an optional container union's None is null too
class A:
    pass


class B:
    pass


def pick(flag: int, a: A, b: B) -> A | B | None:
    if flag == 0:
        return a
    if flag == 1:
        return b
    return None


def box(flag: int, xs: list[int], d: dict[str, int]) -> list[int] | dict[str, int] | None:
    if flag == 0:
        return xs
    if flag == 1:
        return d
    return None


def plain(flag: int, xs: list[int], d: dict[str, int]) -> list[int] | dict[str, int]:
    if flag == 0:
        return xs
    return d


a = A()
b = B()
vals = [pick(0, a, b), pick(1, a, b), pick(2, a, b), pick(0, A(), B()), pick(2, A(), B())]
print([[x is y for y in vals] for x in vals])
print([[x is not y for y in vals] for x in vals])
print([x is a for x in vals], [a is x for x in vals], [x is not b for x in vals], [b is not x for x in vals])
none_a: A | None = None
print([x is none_a for x in vals], [none_a is x for x in vals])
xs = [1]
d = {"k": 1}
cs = [box(0, xs, d), box(1, xs, d), box(2, xs, d), box(0, [1], {"k": 1})]
print([[x is y for y in cs] for x in cs])
print([x is xs for x in cs], [d is not x for x in cs])
ps = [plain(0, xs, d), plain(1, xs, d), plain(0, [1], d)]
print([[x is y for y in ps] for x in ps], [x is not y for x in ps for y in cs])
