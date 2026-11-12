# error: expected tuple[A | B, ...], got tuple[A, ...]
# A tuple's items are objects, a union's are boxes of them: a tuple[A, ...] is no tuple[A | B, ...]
# as it is (its slots would be read as boxes), and is not converted yet
class A:
    pass


class B:
    pass


items: tuple[A, ...] = (A(),)
either: tuple[A | B, ...] = items
print(len(either))
