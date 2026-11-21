# error: expected list[int], got Stack: an object of a class that derives from list is not stored or passed as a list yet
class Stack(list[int]):
    pass


def total(xs: list[int]) -> int:
    return sum(xs)


print(total(Stack([1, 2])))
