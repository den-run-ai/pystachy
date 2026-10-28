# pystachy: python-int
# A generic class's specialization for ints (docs/python-int.md) in a program where another module
# opts in to dynamic Any (dynamic_reader), whose values do not hold promoting ints: its type
# variable binds the 64-bit int there, which the dynamic module reads as its values.
from dynamic_reader import shown
from fixed_generics import Stack

s = Stack(1)
s.push(2)
print(shown(s), s.total(), s.items)
t = Stack(5)
t.push(-7)
print(shown(t), t.peek() - 1, 2 ** 70 + s.pop(), t.total())
