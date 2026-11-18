# With *_ in a sequence pattern, CPython reads each other item once, just before its subpattern,
# and an item after the star at the length the list has then. An __eq__ that changes the list
# while the pattern is matched shows both: an as-pattern and an or-pattern see the item that was
# read, not the one that replaced it, and items after the star are read from the shortened list.
class C:
    def __init__(self, n: int, edit: int) -> None:
        self.n = n
        self.edit = edit

    def __eq__(self, other: object) -> bool:
        if self.edit == 1:
            xs[0] = C(1, 0)  # (replaces the item being matched; it equals nothing)
            return True
        if self.edit == 2:
            xs[0] = C(1, 0)
            return other is K.B
        if self.edit == 3:
            del xs[1:]  # (leaves one item)
            return True
        return False


class K:
    A = C(5, 0)
    B = C(6, 0)


xs: list[C] = [C(0, 1), C(2, 0)]
match xs:
    case [K.A as w, *_]:
        print("as-pattern", w.n, xs[0].n)
    case _:
        print("as-pattern: no")

xs = [C(0, 2), C(2, 0)]
match xs:
    case [K.A | K.B, *_]:
        print("or-pattern", xs[0].n)
    case _:
        print("or-pattern: no")

xs = [C(7, 3), C(8, 0), C(9, 0)]
match xs:
    case [K.A, *_, y, z]:
        print("after the star", y.n, z.n, len(xs))
    case _:
        print("after the star: no")
