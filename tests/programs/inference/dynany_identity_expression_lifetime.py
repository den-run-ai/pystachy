# pystachy: dynamic-any
# Selected locals stay alive after their producing frame returns and through GC.
from typing import Any


def produce(flag: bool) -> list[Any]:
    a = float("1000.25")
    b = float("1000.25")
    chosen = a if flag else b
    return [chosen, a, b]


def callback() -> int:
    scratch: list[Any] = [float("1000.25"), int("1000"), "callback"]
    return len(scratch)


def delayed(flag: bool) -> None:
    a = int("1000")
    b = int("1000")
    objects: list[Any] = [a if flag else b, callback()]
    print(objects[0] is a, objects[0] is b, objects[1])


def verify(flag: bool) -> None:
    objects = produce(flag)
    for i in range(12):
        scratch: list[Any] = [float("1000.25"), int("1000"), str(i)]
        if len(scratch) != 3:
            print("bad scratch")
    print(objects[0] is objects[1], objects[0] is objects[2])
    print(id(objects[0]) == id(objects[1]), id(objects[0]) == id(objects[2]))


verify(True)
verify(False)

delayed(True)
delayed(False)
