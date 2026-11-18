# Different nullable class types still compare two None values by identity. Cover __eq__,
# synthesized != and explicit __ne__; live receivers retain their custom methods.
class Other:
    pass


class Match:
    def __eq__(self, other: Other) -> bool:
        return True


class Unequal:
    def __ne__(self, other: Other) -> bool:
        return True


def other(flag: bool) -> Other | None:
    return Other() if flag else None


def match(flag: bool) -> Match | None:
    return Match() if flag else None


def unequal(flag: bool) -> Unequal | None:
    return Unequal() if flag else None


for fx in [False, True]:
    for fy in [False, True]:
        x = other(fx)
        y = match(fy)
        print(fx, fy, y == x, y != x)
        z = unequal(fy)
        print("ne", fx, fy, z != x)
