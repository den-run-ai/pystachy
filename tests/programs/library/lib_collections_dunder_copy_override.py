# deque.__copy__ is an alias of the base copy, not a call of an override.
from collections import deque


class Queue(deque):
    def copy(self):
        print("override copy called")
        return Queue([99])


class Child(Queue):
    pass


for original in [Queue([1, 2]), Queue([3, 4], 3), Child([5], 2)]:
    duplicate = original.__copy__()
    print(type(duplicate).__name__, list(duplicate), duplicate.maxlen)
    print(list(original), original is duplicate)

print(list(Queue([1]).copy()))
