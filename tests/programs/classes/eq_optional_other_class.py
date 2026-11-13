# == and != of an object | None whose class's __eq__ takes an object of another class, and such
# an object | None: two None values are equal, by identity; None and an object are not
class Other:
    pass


class Match:
    def __eq__(self, other: Other) -> bool:
        return True


def other(flag: bool) -> Other | None:
    return Other() if flag else None


def match(flag: bool) -> Match | None:
    return Match() if flag else None


for fx in [False, True]:
    for fy in [False, True]:
        x = other(fx)
        y = match(fy)
        print(fx, fy, y == x, y != x)
