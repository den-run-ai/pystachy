# deque's C copy uses the actual type, while Counter's Python copy reads __class__.
from collections import Counter, deque


class Queue(deque):
    def __class__(self, source, maxlen: int | None = None):
        print("deque shadow called")
        return deque(source, maxlen)


class Child(Queue):
    pass


for original in [Queue([1, 2]), Queue([3, 4], 3), Child([5], 2)]:
    duplicate = original.copy()
    print(type(duplicate).__name__, list(duplicate), duplicate.maxlen)
    duplicate.append(9)
    print(list(original), list(duplicate), original is duplicate)


class Count(Counter):
    def __class__(self, source):
        print("counter shadow called")
        return Counter("abb")


counts = Count("abb").copy()
print(type(counts).__name__, counts["a"], counts["b"])
