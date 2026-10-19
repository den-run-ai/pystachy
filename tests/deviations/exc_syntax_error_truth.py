# A SyntaxError made of one argument tests that argument's truth as it is made (its __bool__ runs
# then), for the "<no detail available>" of its traceback line, where CPython tests it only when
# it prints that line: here never, so CPython prints no "__bool__". A class object of SyntaxError's
# family does the same; no other exception class tests it (tests/exc_class_call_bool.py)


class Flag:
    def __bool__(self) -> bool:
        print("__bool__")
        return False

    def __str__(self) -> str:
        return "flag"


def make(c: type[Exception], arg: Flag) -> Exception:
    return c(arg)


e = SyntaxError(Flag())
print(type(e).__name__, str(e))
f = make(SyntaxError, Flag())
print(type(f).__name__, str(f))
g = make(IndentationError, Flag())
print(type(g).__name__, str(g))
