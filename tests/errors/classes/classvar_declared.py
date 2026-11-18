# error: classvar_declared.py:6: error: typing.ClassVar (a class attribute) is not supported
from typing import ClassVar


class Op:
    symbol: ClassVar[str]


class Add(Op):
    symbol = "+"


print(Add.symbol)
