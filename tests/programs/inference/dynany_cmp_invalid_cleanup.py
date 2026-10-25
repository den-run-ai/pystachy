# pystachy: dynamic-any
from typing import Any


class Number:
    def __init__(self, mode: int):
        self.mode = mode
        self.payload = 1
        self.items = [4]

    @property
    def value(self):
        print('left operand')
        return self.payload

    def __eq__(self, other):
        print('enter', self.mode)

        def ignored(left, right, unused: int) -> bool:
            print('helper body')
            return left.items == right.items

        try:
            if self.mode == 0:
                return self.items[99] + other.value > 0
            if self.mode == 1:
                return self.value + other.items[99] > 0
            if self.mode == 2:
                return ignored(self, other, self.value + other.value)
            if self.mode == 3:
                return self.value + other.value > 0
            if self.mode == 5:
                return (self.value + other.value) + self.items[99] > 0
            if self.mode == 6:
                return (self.value + other.value) + other.value > 0
            if self.mode == 7:
                return self.value + other.value > 0
            return True  # the invalid operation on the untaken branches is inert
        except IndexError as error:
            print(type(error).__name__, str(error))
            return True
        except TypeError as error:
            print(type(error).__name__, str(error))
            return True
        finally:
            print('cleanup', self.mode)
            if self.mode == 7:
                return False


class Text:
    def __init__(self):
        self.payload = 'x'
        self.items = ['x']

    @property
    def value(self):
        print('right operand')
        return self.payload


right: Any = Text()
for mode in range(8):
    left: Any = Number(mode)
    print(left == right)
