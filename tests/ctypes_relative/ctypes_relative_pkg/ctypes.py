class Function:
    def __init__(self):
        self.argtypes: list[int] = []
        self.restype = 0

    def __call__(self, n: int) -> int:
        return n + 100


class Library:
    def __init__(self):
        self.abs = Function()


class API:
    def __init__(self):
        self.c_int = 0

    def CDLL(self, name: str | None) -> Library:
        return Library()


api = API()
