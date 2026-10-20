# A field first None, given objects by code outside its class.
class Node:
    def __init__(self, v: int) -> None:
        self.v = v
        self.next = None


a = Node(1)
print(a.next is None, a.next)
b = Node(2)
a.next = b
b.next = Node(3)
n = a
total = 0
while n is not None:
    total += n.v
    n = n.next
print(total, a.next is b)
