from collections.abc import Iterator


# for x in o.items() (keys(), values()) of an object whose result's __iter__ yields: the
# generator that __iter__ makes, which the loop owns and closes where it is left


class Bag:
    def __init__(self, xs: list[int]) -> None:
        self.xs = xs

    def __iter__(self) -> Iterator[int]:
        try:
            for x in self.xs:
                yield x
        finally:
            print("closed")


class O:
    def items(self) -> Bag:
        return Bag([1, 2, 3])

    def values(self) -> Bag:
        return Bag([4, 5])


for x in O().items():
    print(x)
    if x == 2:
        break
print("after break")
for x in O().values():
    print(x)
print("after end")
print([y for y in O().items()])
print({y * 2 for y in O().values()})
print(sum(O().values()), list(O().items()))
