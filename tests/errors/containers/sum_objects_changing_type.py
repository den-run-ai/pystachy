# error: sum() of Meter: adding an item to the sum, a Pair, makes a Triple; add the items in a loop, whose variable is annotated with both
class Triple:
    pass


class Pair:
    def __add__(self, other: "Meter") -> Triple:
        return Triple()


class Meter:
    def __radd__(self, other: int) -> Pair:
        return Pair()


print(sum([Meter(), Meter()]))
