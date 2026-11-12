# sum(iterable, start=s) is sum(iterable, s), for numbers and for objects
class Count:
    def __init__(self, n: int) -> None:
        self.n = n

    def __add__(self, other: "Count") -> "Count":
        return Count(self.n + other.n)


def start() -> int:
    print("start")
    return 100


print(sum([1, 2, 3], start=10), sum((i for i in range(4)), start=start()), sum([1.5, 2.5], start=1))
print(sum(range(5), start=2.5), sum([True, False], start=3), sum({1: 2, 3: 4}, start=5))
print(sum([Count(1), Count(2)], start=Count(10)).n)
