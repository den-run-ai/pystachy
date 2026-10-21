# Object protocols dispatch through base annotations and container elements just as named
# methods do. Each override deliberately differs from the base implementation.
class Base:
    def __init__(self, n: int) -> None:
        self.n = n

    def __str__(self) -> str:
        return "base:" + str(self.n)

    def __repr__(self) -> str:
        return "Base(" + str(self.n) + ")"

    def __bool__(self) -> bool:
        return self.n > 0

    def __len__(self) -> int:
        return self.n

    def __eq__(self, other: "Base") -> bool:
        return self.n == other.n

    def __getitem__(self, index: int) -> int:
        return self.n + index

    def __call__(self, extra: int) -> int:
        return self.n + extra


class Child(Base):
    def __str__(self) -> str:
        return "child:" + str(self.n)

    def __repr__(self) -> str:
        return "Child(" + str(self.n) + ")"

    def __bool__(self) -> bool:
        return self.n == 0

    def __len__(self) -> int:
        return self.n + 10

    def __eq__(self, other: Base) -> bool:
        return self.n % 10 == other.n % 10

    def __getitem__(self, index: int) -> int:
        return self.n * 10 + index

    def __call__(self, extra: int) -> int:
        return self.n * 100 + extra


def report(obj: Base) -> None:
    print(str(obj), repr(obj), bool(obj), len(obj), obj[3], obj(4))
    print(obj == Base(12), obj == Base(2), obj != Base(12))


report(Base(2))
report(Child(2))
report(Child(0))
values: list[Base] = [Base(2), Child(2), Child(0)]
print(values)
print([bool(x) for x in values], [len(x) for x in values])
print(Child(12) in values, values.count(Child(12)))
