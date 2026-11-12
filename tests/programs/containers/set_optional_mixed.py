# sets whose element types differ only in None: operators and methods between a set[T], a
# set[T | None] and a set[None] (mypy: metas = {a, b, c} - {None})
class Meta:
    def __init__(self, name: str) -> None:
        self.name = name


def names(s: set[str | None]) -> list[str]:
    return sorted([x for x in s if x is not None])


def strs() -> None:
    plain: set[str] = {"a", "b"}
    opt: set[str | None] = {"b", None, "c"}
    none: set[None] = {None}
    u = plain | opt
    print(names(u), None in u, len(u))
    u2 = opt | plain
    print(names(u2), None in u2, len(u2))
    i = plain & opt
    print(sorted([x for x in i if x is not None]), len(i))
    i2 = opt & plain
    print(names(i2), None in i2, len(i2))
    d = opt - plain
    print(names(d), None in d, len(d))
    d2 = plain - opt
    print(sorted([x for x in d2 if x is not None]), len(d2))
    x = plain ^ opt
    print(names(x), None in x, len(x))
    n = opt - none
    print(names(n), None in n, len(n))
    n2 = opt & none
    print(names(n2), None in n2, len(n2))
    n3 = opt | none
    print(names(n3), None in n3, len(n3))
    n4 = none | opt
    print(names(n4), None in n4, len(n4))
    n5 = none - opt
    print(len(n5), None in n5)
    p = plain | none
    print(names(p), None in p, len(p))
    p2 = none | plain
    print(names(p2), None in p2, len(p2))
    p3 = plain - none
    print(sorted([y for y in p3 if y is not None]), len(p3))
    print(plain == opt, opt == plain, plain <= opt, opt >= plain, plain < opt, opt.isdisjoint(plain), plain.isdisjoint(none), opt.isdisjoint(none))
    print(none <= opt, none == opt, opt > none, none.issubset(opt), opt.issuperset(none), opt.issuperset(plain))
    opt |= plain
    print(names(opt), None in opt)
    opt -= none
    print(names(opt), None in opt)
    opt |= none
    opt &= {"a", None, "zz"}
    print(names(opt), None in opt)
    opt ^= none
    print(names(opt), None in opt)
    opt.update(plain, none, ["q", None])
    print(names(opt), None in opt)
    opt.difference_update(none, ["q"])
    print(names(opt), None in opt)
    opt.intersection_update(plain)
    print(names(opt), None in opt)
    opt.symmetric_difference_update(none)
    print(names(opt), None in opt)
    print(names(opt.union(plain, none)), names(opt.intersection(none)), names(opt.difference(none)), names(opt.symmetric_difference(plain)))
    print(opt.issubset(none), opt.issuperset(none), none.issubset(opt))
    same = {x for x in plain}
    print(same == plain, len(same))


def objects() -> None:
    a = Meta("a")
    b = Meta("b")
    missing: Meta | None = None
    metas = {a, missing, b} - {None}
    print(sorted([m.name for m in metas if m is not None]), None in metas, len(metas))
    with_none = {a, missing, b}
    print(len(with_none), None in with_none, len(with_none & {None}), len(with_none | {None}), len(with_none ^ {None}))
    with_none -= {None}
    print(len(with_none), None in with_none)
    with_none |= {None}
    print(len(with_none), None in with_none, {None} <= with_none, with_none >= {None}, with_none.isdisjoint({None}))
    only = {None} - with_none
    print(len(only))
    just = {None} | {a}
    print(len(just), None in just, a in just, b in just)


def tuples() -> None:
    plain: set[tuple[int, str]] = {(1, "a"), (2, "b")}
    opt: set[tuple[int, str] | None] = {(2, "b"), None}
    u = plain | opt
    print(len(u), None in u, (1, "a") in u, (2, "b") in u)
    d = opt - plain
    print(len(d), None in d)
    d2 = plain - opt
    print(len(d2), (1, "a") in d2)
    print(plain == opt, plain.isdisjoint(opt), (opt - {None}) <= plain)


strs()
objects()
tuples()
