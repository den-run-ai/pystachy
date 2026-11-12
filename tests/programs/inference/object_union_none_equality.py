# A union that holds objects beside scalars compared with None: the member's own comparison,
# as for a class's object. An object's __eq__ is asked about None; a number is never None.


class Blank:
    def __eq__(self, other: object) -> bool:
        return other is None

    def __hash__(self) -> int:
        return 1

    def __lt__(self, other: object) -> bool:
        return other is None


class Plain:
    def __init__(self, n: int) -> None:
        self.n = n


def blank(x: "int | Blank") -> None:
    print(x == None, None == x, x != None, None != x)


def plain(x: "str | Plain") -> None:
    print(x == None, None == x, x != None, None != x)


def held(i: int) -> "float | Blank":
    if i == 0:
        return Blank()
    if i == 1:
        return 2.5
    return None


def orders(x: "int | Blank") -> None:
    try:
        print(x < None)
    except TypeError as error:
        print("TypeError:", error)


def same(a: Blank) -> None:
    print(a == None, None == a, a != None, None != a)


blank(Blank())
blank(7)
plain(Plain(1))
plain("text")
for n in range(3):
    value = held(n)
    print(value == None, None == value, value != None, value is None)
orders(Blank())
orders(3)
same(Blank())
