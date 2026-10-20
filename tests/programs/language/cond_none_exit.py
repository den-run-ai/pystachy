# conditional expressions and and/or with None arms, None-returning calls, and sys.exit() as an operand
import sys


class Config:
    def __init__(self, name: str):
        self.name = name


def load(ok: bool) -> Config | None:
    return Config("main") if ok else None


def pick(n: int) -> Config | None:
    return None if n > 1 else Config("p" + str(n))


def f(n: int) -> int:
    x = sys.exit(4) if n > 5 else 2
    return x + n


def g(n: int) -> bool:
    return n < 3 and sys.exit(5)


def h() -> None:
    print("h")


cfg = load(True) or sys.exit("no config")
print(cfg.name)
print(pick(1) is None, pick(2) is None)
print(f(1), g(7))
if f(0) > 1 or sys.exit(8):
    print("yes")
print(None or None, h() or h(), h() and h())
cfg2 = load(False) or sys.exit("no config")
print("not reached")
