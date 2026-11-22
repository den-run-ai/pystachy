# error: expected int, got str
class Stack(list):
    pass


s = Stack()
s.append(1)
s.append("two")
