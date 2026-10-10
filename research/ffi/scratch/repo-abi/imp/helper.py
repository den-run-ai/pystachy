class Pt:
    def __init__(self, x: int, ok: bool) -> None:
        self.x = x
        self.ok = ok
        self.n: int | None = None


def scale(p: Pt, k: int) -> int:
    return p.x * k


TABLE: list[str] = ["a"]
