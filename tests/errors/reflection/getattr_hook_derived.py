# error: getattr_hook_derived.py:19: error: reading field 'n', which may be unassigned, of a Base is not supported where Sub, which derives from it, defines __getattr__ (CPython calls it for an object of that class): define __getattr__ in Base, or narrow the object with isinstance()
# Code compiled for a base class without __getattr__ raises AttributeError for an unassigned
# field; CPython calls the __getattr__ that a derived class adds (#1536), here for a Sub, whose
# __init__ does not call its base's, so the read is rejected.
class Base:
    def __init__(self) -> None:
        self.n = 1


class Sub(Base):
    def __init__(self) -> None:
        self.m = 2

    def __getattr__(self, name: str) -> int:
        return 0


def show(b: Base) -> None:
    print(b.n)


show(Base())
show(Sub())
