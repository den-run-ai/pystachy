from dataclasses import dataclass

class P:
    def __init__(self, x: int, s: str) -> None:
        self.x = x
        self.s = s
        self.f = 1.5

    def get(self) -> int:
        return self.x


def add(a: int, b: float, c: bool, s: str, l: list[int], d: dict[str, int], t: tuple[int, str], p: P, o: int | None, os_: str | None, op: P | None) -> float:
    return a + b


def nothing() -> None:
    print("x")


def mk(n: int) -> list[str]:
    return [str(n)]


print(add(1, 2.0, True, "s", [1], {"a": 1}, (1, "x"), P(1, "a"), None, None, None))
nothing()
print(mk(3))
print(P(2, "b").get())
