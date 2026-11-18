# error: closed union method calls require narrowing with isinstance() first
# A method needs the member: an int has none of Meter's.
class Meter:
    def reading(self) -> int:
        return 1


def read(value: "int | Meter") -> int:
    return value.reading()


print(read(Meter()))
