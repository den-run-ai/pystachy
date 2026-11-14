# Tuple searches preserve reflected comparison fallback through the lenient
# template dispatch used for runtime classes.
class Base:
    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other) -> bool:
        print("base", self.value)
        if not isinstance(other, Base) or self.value < 0:
            return NotImplemented
        return self.value == other.value


class Child(Base):
    def __eq__(self, other) -> bool:
        print("child", self.value)
        if not isinstance(other, Child) or self.value < 0:
            return NotImplemented
        return self.value == other.value


def search(needle: Base, item: Base) -> None:
    print(needle in (item,), (item, item).count(needle))
    try:
        print((item,).index(needle))
    except ValueError:
        print("missing")


search(Base(1), Child(1))
search(Child(1), Base(1))
search(Base(2), Child(1))
search(Child(-1), Base(-1))
same = Child(-1)
search(same, same)
search(None, Child(1))
search(Child(1), None)
