# A module that does not opt in: its tuples hold checked 64-bit ints.
def add_pair(t: tuple[int, int]) -> int:
    return t[0] + t[1]


def swap(t: tuple[int, int]) -> tuple[int, int]:
    return t[1], t[0]
