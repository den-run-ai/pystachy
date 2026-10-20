from dataclasses import dataclass


class Flag:
    def __init__(self) -> None:
        self.on = True

    def __bool__(self) -> bool:
        print("tested")
        return self.on


FROZEN = Flag()


@dataclass(frozen=FROZEN)
class Point:
    x: int

    def moved(self, *a):
        return a
