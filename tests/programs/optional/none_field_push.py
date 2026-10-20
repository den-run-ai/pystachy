# A field first None, read and then stored in one method (n.next = self.head, then
# self.head = n): the store further on in the method types it.
class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.next = None


class Stack:
    def __init__(self) -> None:
        self.head = None
        self.size = 0

    def push(self, v: int) -> None:
        n = Node(v)
        n.next = self.head
        self.head = n
        self.size += 1

    def pop(self) -> int:
        h = self.head
        if h is None:
            raise IndexError("pop from empty stack")
        self.head = h.next
        self.size -= 1
        return h.v


s = Stack()
for i in range(4):
    s.push(i * i)
print(s.size, s.pop(), s.pop(), s.size)
try:
    Stack().pop()
except IndexError as e:
    print("IndexError:", e)
