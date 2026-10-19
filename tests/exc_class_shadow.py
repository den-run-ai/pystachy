# A class or def of the main program that has a builtin's name is the program's, also through an
# alias (C = ValueError), which does not name the builtin, and its class shows its module


class ValueError(Exception):
    pass


def len(s: str) -> int:
    return 42


class zip:
    def __init__(self) -> None:
        self.x = 1


C = ValueError
L = len
Z = zip
print(C is ValueError, C.__name__, C.__module__, C.__qualname__)
try:
    raise C("x")
except ValueError as e:
    print("the program's", type(e).__name__, e)
except Exception as e:
    print("the builtin", type(e).__name__, e)
print(type(C("y")) is ValueError, str(type(C("z"))))
print(L("ab"), len("ab"), Z().x)


class CM:
    def __enter__(self) -> "CM":
        return self

    def __exit__(self, et, ev, tb) -> bool:
        print(str(et), et is ValueError)
        return True


with CM():
    raise ValueError("w")
