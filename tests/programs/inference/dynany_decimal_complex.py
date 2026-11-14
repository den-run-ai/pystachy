# pystachy: dynamic-any
from decimal import Decimal
from typing import Any


def compare(left: Any, right: Any) -> None:
    print(left == right, right == left, left != right, right != left)
    print(left in (right,), right in (left,))


compare(Decimal("1.5"), 1.5 + 0j)
compare(Decimal("1.1"), 1.1 + 0j)
compare(Decimal("NaN"), 1 + 0j)
compare(Decimal("sNaN"), 1 + 2j)
