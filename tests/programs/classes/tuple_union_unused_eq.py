class A:
    def __eq__(self, other: object) -> bool:
        return other.missing()


class B:
    pass


def search(x: A | B, y: A | B) -> None:
    print(x in (y,), (y,).count(x))
    if x in (y,):
        print((y,).index(x))


b = B()
search(B(), B())
search(b, b)
search(None, None)
