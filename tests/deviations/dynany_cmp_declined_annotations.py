# pystachy: dynamic-any
# Same-class dynamic comparisons must reject an unavailable typed method rather
# than silently use identity or try a lower-priority reflected method.
from typing import Any


class Declared:
    def __eq__(self, other: int) -> bool:
        print("eq body")
        return True

    def __ne__(self, other: int) -> bool:
        print("ne body")
        return False

    def __lt__(self, other: int) -> bool:
        print("lt body")
        return True

    def __le__(self, other: int) -> bool:
        print("le body")
        return True

    def __gt__(self, other: "Declared") -> bool:
        print("gt body")
        return False

    def __ge__(self, other: "Declared") -> bool:
        print("ge body")
        return False


class Inverted:
    def __eq__(self, other: int) -> bool:
        print("inverted body")
        return True


left: Any = Declared()
right: Any = Declared()
for op in range(4):
    try:
        if op == 0:
            print(left == right)
        elif op == 1:
            print(left != right)
        elif op == 2:
            print(left < right)
        else:
            print(left <= right)
    except TypeError as error:
        print(op, str(error))
    finally:
        print("cleanup", op)

# Supported methods and calls to the declared operand type remain available.
print(left > right, left >= right, left == 1)
first: Any = Inverted()
second: Any = Inverted()
try:
    print(first != second)
except TypeError as error:
    print("inverted", str(error))
items: list[Any] = [left]
print(left in items)  # container identity must not call __eq__
try:
    print(right in items)
except TypeError as error:
    print("membership", str(error))
