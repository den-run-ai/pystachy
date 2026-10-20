# An except clause's classes are looked up when an exception gets to the clause: a class whose
# class statement has not run yet raises NameError there (where no exception gets to the clause,
# nothing is looked up).
def f() -> None:
    try:
        raise KeyError("x")
    except Unready:
        print("unready")
    except KeyError:
        print("key")


try:
    f()
except NameError as e:
    print("NameError:", e)
try:
    raise KeyError("y")
except KeyError:
    print("fine")
except Unready:
    print("not reached")
try:
    print("no exception")
except (ValueError, Unready):
    pass
try:
    try:
        raise OSError("o")
    except (Unready, OSError):
        print("never")
except NameError as e:
    print("NameError:", e)


class Unready(Exception):
    pass


f()
try:
    raise Unready("u")
except Unready as e:
    print("caught", repr(e))
