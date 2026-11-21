# A test does not narrow an attribute of a global: the read after it is the union's, whose
# int the + selects by its tag.
class Ref:
    def __init__(self, value: int | str) -> None:
        self.value = value


ref = Ref(1)


def bump() -> int:
    if isinstance(ref.value, int):
        return ref.value + 1
    return 0


print(bump())
