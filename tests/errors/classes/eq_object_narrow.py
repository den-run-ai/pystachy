# error: __eq__() of Money cannot compare an operand of type Token
# t == m calls Money.__eq__(m, t), reflected, as Token has no __eq__: CPython runs it with the Token
# whatever its annotation says, which a method annotated to take only a Money cannot be compiled for
class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __eq__(self, other: "Money") -> bool:
        return self.cents == other.cents


class Token:
    def __init__(self, cents: int) -> None:
        self.cents = cents


def same(t: Token, m: Money) -> bool:
    return t == m


print(same(Token(1), Money(1)))
