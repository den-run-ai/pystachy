# Documented deviation: gc.collect() returns 0. CPython returns the number of unreachable
# objects its cycle collector found, here those of a cycle of two objects.
import gc


class Node:
    def __init__(self) -> None:
        self.other: Node | None = None


def cycle() -> None:
    a = Node()
    b = Node()
    a.other = b
    b.other = a


gc.collect()
cycle()
print(gc.collect())
