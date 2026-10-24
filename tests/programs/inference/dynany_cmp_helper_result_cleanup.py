# pystachy: dynamic-any
from typing import Any


def same(value):
    print('same')
    return value


def values(value):
    print('values')
    result = value.items
    return result


class Left:
    def __init__(self):
        self.payload = [1]

    @property
    def items(self):
        print('left items')
        return self.payload

    def __eq__(self, other):
        try:
            original = same(other)
            result = values(original)
            result.clear()
            return self.items == original.items
        finally:
            print('cleanup')


class Right:
    def __init__(self, fail: bool):
        self.payload = ['x']
        self.fail = fail

    @property
    def items(self):
        print('right items')
        if self.fail:
            raise ValueError('getter first')
        return self.payload


class Missing:
    pass


left: Any = Left()
right = Right(False)
saved = right.payload
other: Any = right
print(left == other)
print(saved, right.payload, saved is right.payload)
for value in [Right(True), Missing()]:
    try:
        print(left == value)
    except ValueError as error:
        print(str(error))
    except AttributeError as error:
        print(str(error))

# The ordinary typed specialization keeps its getter and native return.
print(values(right) is saved)
