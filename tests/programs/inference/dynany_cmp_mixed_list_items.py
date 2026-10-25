# pystachy: dynamic-any
from typing import Any


class Left:
    def __init__(self, action: int, result: bool):
        self.action = action
        self.result = result

    def __eq__(self, other: Any) -> bool:
        print('element', self.action, self.result)
        if self.action == 1:
            left.clear()
            right.clear()
        elif self.action == 2:
            left.clear()
        elif self.action == 3:
            left.append(Left(0, True))
            right.append(Right())
        elif self.action == 4:
            raise ValueError('element comparison')
        return self.result


class Right:
    pass


left: list[Left] = [Left(0, True)]
right: list[Right] = [Right()]
print(left == right, right == left, left != right)
left[0].result = False
print(left == right, left != right)
right.append(Right())
print('different lengths', left == right)
left.clear()
right.clear()
print('empty', left == right)
for action in [1, 2, 3]:
    for result in [False, True]:
        left = [Left(action, result)]
        right = [Right()]
        print('mutation', action, result, left == right, len(left), len(right))
left = [Left(4, True)]
right = [Right()]
try:
    print(left == right)
except ValueError as error:
    print(error)

ints = [3]
boxed: list[Any] = [3]
print('boxed numbers', ints == boxed, boxed == ints)
boxed.append('x')
print('boxed lengths', ints != boxed)
nan = float('nan')
floats = [nan]
boxed_nan: list[Any] = [nan]
print('same nan', floats == boxed_nan, boxed_nan == floats)
boxed_nan[0] = float('nan')
print('distinct nan', floats == boxed_nan, boxed_nan == floats)
text = ['abc']
boxed_text: list[Any] = ['abc']
print('boxed strings', text == boxed_text, boxed_text == text)
byte_values = [b'abc']
print('bytes versus strings', byte_values == text, text == byte_values)


class Reflected:
    def __eq__(self, other: Any) -> bool:
        print('reflected None', other is None)
        return True


nullable: list[Right] = [None]
reflected: list[Reflected] = [Reflected()]
print('null class', nullable == reflected, reflected == nullable)
