# == and != between a union holding complex numbers and an object of another class: complex's
# __eq__ declines the object (CPython's returns NotImplemented), so the object's own __eq__
# answers, else identity
class Equal:
    def __eq__(self, other: object) -> bool:
        print("Equal.__eq__")
        return True


class Plain:
    pass


def optional(v: complex | None) -> None:
    e = Equal()
    p = Plain()
    print(v == e, e == v, v != e, e != v)
    print(v == p, p == v, v != p, p != v)


def numbers(v: int | complex) -> None:
    # (with v on the left: complex_union_object_left_eq.py; an int member and a Plain on either
    # side compare by identity, as 1 == Plain() and Plain() == 1 do:
    # complex_union_object_cmp.py)
    e = Equal()
    print(e == v, e != v)


optional(1j)
optional(None)
numbers(1)
numbers(2 + 0j)
