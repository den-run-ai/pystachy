from dataclasses import dataclass


def flag():
    print("flag called")
    return True


@dataclass(frozen=flag())
class Point:
    x: int

    def moved(self, *a):
        return a
