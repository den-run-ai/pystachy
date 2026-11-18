# error: closed union arithmetic requires narrowing with isinstance() first: narrow it to one of its types first, with isinstance()
# Arithmetic selects a number's or an object's operation; a str member has none to select.
class Meter:
    def __add__(self, other: int) -> "Meter":
        return self


def bump(value: "str | Meter") -> None:
    print(value + 1)


bump(Meter())
