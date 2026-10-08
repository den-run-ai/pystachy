# return f() in a function declared -> None, where f returns None
import sys


def log(msg: str) -> None:
    print(msg)


def warn(msg: str) -> None:
    return log("warning: " + msg)


class Box:
    def __init__(self):
        self.xs: list[int] = []

    def add(self, x: int) -> None:
        return self.xs.append(x)


def quit_now(m: str) -> None:
    return sys.exit(m)


warn("disk")
b = Box()
b.add(3)
print(b.xs)
quit_now("bye")
