# complex numbers as a union's member and inside a container member: each member's descriptor is
# delimited from the next member's tag, so each value prints as CPython prints it
def show(x: complex | list[complex]) -> None:
    print(repr(x), [x], x, f"{x}")


def pair(x: list[complex] | dict[str, complex] | int) -> None:
    print(repr(x), [x])


show(2j)
show([1j, 2 + 0j])
pair([3j])
pair({"k": 1 - 1j})
pair(4)
