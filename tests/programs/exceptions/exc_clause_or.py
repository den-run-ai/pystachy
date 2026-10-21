# except A or B catches A (a class is true), except A and B catches B, as CPython evaluates them.
class E(Exception):
    pass


def boom(i: int) -> None:
    if i == 0:
        raise E("e")
    if i == 1:
        raise KeyError("k")
    raise ValueError("v")


for i in range(3):
    try:
        boom(i)
    except E or KeyError as e:
        print("E", repr(e))
    except KeyError and ValueError:
        print("V")
    except (KeyError) or (IndexError):
        print("K")
