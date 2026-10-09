# error: the value assigned to field 'name' (str) may be None (str | None); test it with 'is not None' first
class User:
    def __init__(self, name: str):
        self.name = name


def rename(u: User, n: str | None) -> None:
    u.name = n


rename(User("a"), "b")
