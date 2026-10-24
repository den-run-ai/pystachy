# pystachy: dynamic-any
from typing import Any


def attempt(left, right, mode: int) -> bool:
    print('enter', mode)
    try:
        try:
            if mode == 0:
                return left.items[0] + right.items[0] > 0
            if mode == 1:
                return left.items[0] - right.items[0] > 0
            if mode == 2:
                return left.items[0] < right.items[0]
            if mode == 3:
                return ~right.items[0] > 0
            if mode == 4:
                return left.indices[right.items[0]] > 0
            return left.items[0] << right.items[0] > 0
        except ValueError:
            print('wrong handler')
            return False
        except TypeError as error:
            print(type(error).__name__, str(error))
            return True
        finally:
            print('inner cleanup', mode)
    finally:
        print('outer cleanup', mode)


class Number:
    def __init__(self):
        self.payload = [1]
        self.indices = [4, 5]

    @property
    def items(self):
        print('left operand')
        return self.payload

    def __eq__(self, other):
        return attempt(self, other, 0)

    def __ne__(self, other):
        return attempt(self, other, 1)

    def __lt__(self, other):
        return attempt(self, other, 2)

    def __le__(self, other):
        return attempt(self, other, 3)

    def __gt__(self, other):
        return attempt(self, other, 4)

    def __ge__(self, other):
        return attempt(self, other, 5)


class Text:
    def __init__(self):
        self.payload = ['x']
        self.indices = [4, 5]

    @property
    def items(self):
        print('right operand')
        return self.payload


left: Any = Number()
right: Any = Text()
print(left == right)
print(left != right)
print(left < right)
print(left <= right)
print(left > right)
print(left >= right)
# Reverse dispatch invokes the corresponding reflected operation.
print(right == left)
print(right != left)
print(right < left)
print(right <= left)
print(right > left)
print(right >= left)
# A separately instantiated ordinary typed helper keeps its normal behavior.
print(attempt(Number(), Number(), 0))
