# A module the program imports, whose code and functions import in try statements
# (tests/programs/imports/import_try_binding*.py)
import good


def boom() -> None:
    raise ValueError("boom")


try:
    boom()
    from good import A2 as ua2
except ValueError:
    print("user: from good import A2 as ua2 skipped")


def use() -> int:
    return ua2()


def load_bad() -> int:
    try:
        import bad as lb
    except ValueError as e:
        print("user.load_bad: import failed:", e)
    return lb.Y


def load_good() -> int:
    try:
        import good as lg
    except ValueError:
        print("not reached")
    return lg.A
