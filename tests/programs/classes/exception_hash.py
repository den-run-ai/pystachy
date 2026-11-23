# hash() of an exception: by identity, as CPython's BaseException hashes, a class's own __hash__,
# or TypeError where its class defines __eq__ and no __hash__; also held by a value of object, whose
# hash() a program with an exception stored as object may ask of any value
class Oops(Exception):
    pass


class Keyed(Exception):
    def __hash__(self) -> int:
        return 7


class Compared(Exception):
    def __eq__(self, other: object) -> bool:
        return False


def main() -> None:
    e = Oops("x")
    print(hash(e) == hash(e), hash(e) == hash(Oops("x")))
    held: object = e
    print(hash(held) == hash(e), hash(Keyed("k")))
    try:
        raise ValueError("v")
    except ValueError as err:
        print(hash(err) == hash(err))
    try:
        print(hash(Compared("c")))
    except TypeError as t:
        print("TypeError", t)
    values: list[object] = [e, 5, "s", Keyed("y"), (1, "t")]
    print([hash(v) == hash(v) for v in values], hash(values[3]))


main()
