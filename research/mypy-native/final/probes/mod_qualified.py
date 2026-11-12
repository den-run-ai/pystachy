import typing
import typing as t
from typing import Final as F
X: typing.Final = 3
Y: t.Final[int] = 4
Z: F = 5
W: F[str] = "w"
print(X, Y, Z, W)
