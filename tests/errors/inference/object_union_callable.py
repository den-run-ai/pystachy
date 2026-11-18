# error: callable() of a Handler | int is not supported
# A union of objects and scalars holds no Callable: its tag tells a member's class, not whether
# the object is callable (a reference union's callable() is not supported either).
class Handler:
    def __call__(self) -> int:
        return 1


def check(x: int | Handler) -> None:
    print(callable(x))


check(Handler())
