# A tuple's in, count() and index() where the items or the value searched for are a union of
# objects and scalars (int | Item | None): None matches only None, a number another equal number,
# an object itself or what its class's __eq__ finds equal, whichever side it is on
class Item:
    pass


class Seven:
    def __eq__(self, other: object) -> bool:
        return isinstance(other, int) and other == 7


def search(x: int | Item | None, t: tuple[int | Item | None, int | Item | None]) -> None:
    print(x in t, x not in t, t.count(x))


def where(x: int | Item | None, t: tuple[int | Item | None, int | Item | None, int | Item | None]) -> int:
    return t.index(x)


def plain(t: tuple[int | Item | None, int | Item | None], item: Item) -> None:
    print(1 in t, item in t, None in t)


def sevens(x: int | Seven, t: tuple[int | Seven, int]) -> None:
    print(x in t, t.count(x))


item = Item()
search(None, (item, 1))
search(item, (None, item))
search(1, (None, item))
search(None, (None, 1))
search(2, (item, 2))
search(Item(), (item, None))
print(where(3, (item, 3, None)), where(None, (item, 3, None)), where(item, (None, 3, item)))
plain((None, 1), item)
plain((item, 2), item)
sevens(7, (Seven(), 1))
sevens(Seven(), (7, 7))
sevens(8, (Seven(), 8))
