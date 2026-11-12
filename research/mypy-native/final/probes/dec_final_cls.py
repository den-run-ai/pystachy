from typing import final
import typing
@final
class A:
    x = 1
@typing.final
class B:
    x = 2
print(A.x, B.x, A().x)
