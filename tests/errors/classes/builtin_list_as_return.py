# error: expected list[int], got Stack: an object of a class that derives from list is not stored or passed as a list yet
class Stack(list[int]):
    pass


def make() -> list[int]:
    return Stack([1, 2])


print(make())
