# pystachy: dynamic-any
from typing import Any


class Expression:
    pass


class Statement:
    def emit(self, value: int = 2) -> int:
        return value


class Visitor(Expression, Statement):
    def emit(self, value: int = 20) -> int:
        return value + 1


def role_method(visitor: Statement) -> Any:
    return visitor.emit


def concrete_method(visitor: Visitor) -> Any:
    return visitor.emit


def dynamic_method(visitor: Any) -> Any:
    return visitor.emit


visitor = Visitor()
a = role_method(visitor)
b = concrete_method(visitor)
c = dynamic_method(visitor)
print(a(), b(), c(value=5))
print(a == b, b == c, a == c, a is b)
print({a: 19}.get(b, 0), a == role_method(Visitor()))
