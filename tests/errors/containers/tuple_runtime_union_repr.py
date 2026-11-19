# error: closed union operations require narrowing with isinstance() first
# repr() of a tuple of union items, as of a union value, needs its items narrowed first
class A:
    def __repr__(self) -> str:
        return "A()"


class B:
    def __repr__(self) -> str:
        return "B()"


mixed: tuple[A | B, ...] = (A(), B())
print(mixed)
