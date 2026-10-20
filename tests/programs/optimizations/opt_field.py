# A field that __init__ types str, given a str | None by another function: str | None.
class User:
    def __init__(self, name: str):
        self.name = name


def rename(u: User, n: str | None) -> None:
    u.name = n


u = User("a")
rename(u, "b")
print(u.name)
rename(u, None)
print(u.name)
