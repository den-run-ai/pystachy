# This module deliberately uses ordinary typed storage, without dynamic Any.
class Imported:
    default: float = float("nan")

    def __init__(self) -> None:
        self.n: int = int("1000")

    def rebind(self) -> None:
        self.n = int("1000")
