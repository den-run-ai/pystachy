# callable() of a union of objects and scalars whose classes define no __call__: false for every
# member, and for None
class Item:
    pass


def check(x: int | Item | None, y: str | Item) -> None:
    print(callable(x), callable(y))


check(1, "a")
check(Item(), Item())
check(None, "b")
