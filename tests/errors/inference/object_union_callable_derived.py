# error: callable() of a Base | int is not supported
# A class derived from a member may define __call__, which the member's tag does not tell.
class Base:
    pass


class Handler(Base):
    def __call__(self) -> int:
        return 1


def check(x: int | Base) -> None:
    print(callable(x))


check(Handler())
