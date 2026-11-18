# A tuple[A, ...] converted where a tuple[A | B, ...] is wanted is a new tuple of the items' union
# boxes (as other tuple conversions make: tuple_runtime_identity.py); CPython passes the tuple
# itself on
class A:
    pass


class B:
    pass


def build(n: int) -> tuple[A, ...]:
    return tuple(A() for _ in range(n))


items = build(2)
widened: tuple[A | B, ...] = items
print("widened", len(widened) == len(items), widened is items)
