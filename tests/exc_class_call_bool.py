# A call of a class object, whose class is known only when it runs, tests its argument's truth only
# for SyntaxError's family (which this test leaves out): a __bool__ or __len__ of the program is
# not called, as in CPython


class Flag:
    def __bool__(self) -> bool:
        print("__bool__")
        return False

    def __str__(self) -> str:
        return "flag"

    def __repr__(self) -> str:
        return "Flag()"


class Sized:
    def __len__(self) -> int:
        print("__len__")
        return 0

    def __str__(self) -> str:
        return "sized"

    def __repr__(self) -> str:
        return "Sized()"


def make(c: type[Exception], arg: Flag) -> Exception:
    return c(arg)


def make_sized(c: type[Exception], arg: Sized) -> Exception:
    return c(arg)


for c in [ValueError, KeyError, RuntimeError]:
    e = make(c, Flag())
    print(type(e).__name__, str(e), repr(e))
    s = make_sized(c, Sized())
    print(type(s).__name__, str(s), repr(s))
