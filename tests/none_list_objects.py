# pyperformance float's shape: points = [None] * n, then points[i] = Point(i).
from math import cos, sin


class Point:
    def __init__(self, i: int) -> None:
        self.x: float = sin(i)
        self.y: float = cos(i) * 3


def benchmark(n: int) -> float:
    points = [None] * n
    for i in range(n):
        points[i] = Point(i)
    total = 0.0
    for p in points:
        total += p.x + p.y
    return total


print(round(benchmark(100), 6))
