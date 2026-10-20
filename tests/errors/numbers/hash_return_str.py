# error: hash_return_str.py:7: error: __hash__ must return int
# (CPython raises TypeError: __hash__ method should return an integer, where the hash is taken)
class Name:
    def __init__(self, s: str) -> None:
        self.s = s

    def __hash__(self) -> str:
        return self.s


print(len({Name("a")}))
