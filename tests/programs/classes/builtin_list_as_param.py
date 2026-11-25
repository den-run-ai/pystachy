class Stack(list[int]):
    pass


def total(xs: list[int]) -> int:
    return sum(xs)


print(total(Stack([1, 2])))
