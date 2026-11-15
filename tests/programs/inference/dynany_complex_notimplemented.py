# pystachy: dynamic-any
from typing import Any


class Declines:
    def __eq__(self, other) -> bool:
        print("eq")
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("ne")
        return NotImplemented


def compare(left: Any, right: Any) -> None:
    print(left == right, right == left, left != right, right != left)
    print(left in (right,), right in (left,), (right, right).count(left))


compare(1j, Declines())
compare(1j, None)
compare(None, Declines())
compare(None, None)
