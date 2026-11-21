# error: Stack() takes at most one argument, an iterable of its items (as list() does)
class Stack(list[int]):
    pass


s = Stack([1], [2])
