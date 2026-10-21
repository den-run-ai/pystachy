class Counted:
    made = 0

    def __new__(cls, n: int) -> "Counted":
        print("new called")
        Counted.made += 1
        return object.__new__(cls)

    def __init__(self, n: int) -> None:
        self.n = n


def double(x: int) -> int:
    return 2 * x
