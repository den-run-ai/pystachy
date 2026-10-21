class Named:
    def __init__(self) -> None:
        self.n = 0

    def __set_name__(self, owner: object, name: str) -> None:
        print("set_name", name)


D = Named()


class Pair:
    "CPython calls D.__set_name__ for the class attribute a"
    a, b = D, 1

    def get(self, *a):
        return a
