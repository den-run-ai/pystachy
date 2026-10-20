# error: expected dict, got dictionary
class dictionary:
    def __init__(self, n: int) -> None:
        self.n = n


def f(flag: bool) -> None:
    out = {}
    if flag:
        out = dictionary(3)
    print(out.n)


f(False)
