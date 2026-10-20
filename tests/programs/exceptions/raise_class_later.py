# raise looks its exception class up first, as a call of the class does: before the class
# statement has run, raise C(...), a bare raise C and raise ... from C(...) raise NameError
def made() -> None:
    raise LateErr("x")


def bare() -> None:
    raise LateErr


def cause() -> None:
    raise ValueError("v") from LateErr("c")


for k in range(3):
    try:
        if k == 0:
            made()
        elif k == 1:
            bare()
        else:
            cause()
    except NameError as e:
        print("NameError:", e)


class LateErr(Exception):
    pass


try:
    made()
except LateErr as e:
    print("LateErr:", e)
try:
    bare()
except LateErr as e:
    print("LateErr:", repr(e))
try:
    cause()
except ValueError as e:
    print("ValueError:", e)
