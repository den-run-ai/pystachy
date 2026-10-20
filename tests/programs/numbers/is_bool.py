# `is` and `is not` between bools: a bool is one of CPython's two objects, True and False
def check(flag: bool, other: bool) -> str:
    out = ""
    out += "T" if flag is True else "-"
    out += "F" if flag is False else "-"
    out += "n" if flag is not True else "-"
    out += "s" if flag is other else "-"
    out += "d" if flag is not other else "-"
    return out


for a in [True, False]:
    for b in [True, False]:
        print(a, b, check(a, b), a is b, a is not b, (a and b) is True, (not a) is False)


class Opts:
    def __init__(self, verbose=False, hyphens=True):
        self.verbose = verbose
        self.hyphens = hyphens

    def mode(self) -> str:
        if self.hyphens is True and self.verbose is not True:
            return "hyphens"
        return "plain"


print(Opts().mode(), Opts(True).mode(), Opts(hyphens=False).mode())
xs = [1, 2, 3]
print((len(xs) > 2) is True, (3 in xs) is not False, isinstance(xs, list) is True)
