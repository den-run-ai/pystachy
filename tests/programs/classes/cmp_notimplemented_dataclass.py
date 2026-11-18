# A dataclass's own ordering method that returns NotImplemented, beside the __eq__ it is given.
from dataclasses import dataclass


@dataclass
class Money:
    cents: int

    def __lt__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return self.cents < other.cents


@dataclass
class Weight:
    grams: int

    def __gt__(self, other):
        if isinstance(other, Money):
            return self.grams > other.cents
        return NotImplemented


m = [Money(5), Money(3), Money(5)]
print(m[0] < m[1], m[1] < m[0], m[0] == m[2], m[0] == m[1], sorted(m)[0].cents, min(m).cents)
w = [Weight(4)]
print(m[0] < w[0], m[1] < w[0])
try:
    print(w[0] > w[0])
except TypeError as e:
    print("TypeError", e)
