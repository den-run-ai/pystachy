# error: closed union arithmetic requires narrowing with isinstance() first: copy it to a local variable, and narrow that to one of its types with isinstance() (a test does not narrow a global, nor a field past a call or a store that may change it)
class Ref:
    def __init__(self, value: int | str) -> None:
        self.value = value


ref = Ref(1)


def bump() -> int:
    if isinstance(ref.value, int):
        return ref.value + 1
    return 0


print(bump())
