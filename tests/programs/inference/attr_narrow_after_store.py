# A store to an attribute of that name voids the narrowing of e.value: the read after it is
# the union's again, whose str then has no + with an int, as in CPython.
class Ref:
    def __init__(self, value: int | str) -> None:
        self.value = value


def bump(e: Ref, other: Ref) -> int:
    if isinstance(e.value, int):
        other.value = "text"
        return e.value + 1
    return 0


r = Ref(1)
print(bump(r, r))
