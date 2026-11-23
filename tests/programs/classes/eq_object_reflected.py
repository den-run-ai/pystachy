# == and != between objects of two classes, neither derived from the other and neither with a
# subclass: the left operand's method, else the right operand's reflected one, as CPython calls them
class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            print("Money.__eq__(Money)")
            return self.cents == other.cents
        if isinstance(other, Token):
            print("Money.__eq__(Token)")
            return self.cents == other.n
        print("Money.__eq__(other)")
        return False


class Token:
    def __init__(self, n: int) -> None:
        self.n = n


class Price:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def __eq__(self, other: object) -> bool:
        print("Price.__eq__")
        return isinstance(other, Token) and other.n == self.cents

    def __ne__(self, other: object) -> bool:
        print("Price.__ne__")
        return isinstance(other, Token) and other.n != self.cents


class Plain:
    pass


def same(x, y) -> bool:
    return x == y


def differ(x, y) -> bool:
    return x != y


def token(n: int) -> Token:
    print("token", n)
    return Token(n)


def money(n: int) -> Money:
    print("money", n)
    return Money(n)


def main() -> None:
    t = Token(5)
    m = Money(5)
    p = Price(7)
    # the right operand's __eq__, with the operands swapped; != by its __eq__ where it has no __ne__
    print(t == m, t != m)
    print(Token(6) == m, Token(6) != m)
    # ... and its own __ne__ where it has one
    print(t == p, t != p)
    print(Token(7) == p, Token(7) != p)
    # the left operand's own method, as before
    print(m == t, m != t, m == p, p == m, p != m)
    # no method: never the same object
    print(t == Plain(), t != Plain(), Plain() == t, Plain() != t)
    # function templates, compiled for each pair of classes
    print(same(t, m), same(m, t), same(t, p), same(t, Plain()), same(t, t))
    print(differ(t, m), differ(t, p), differ(Plain(), t))
    # operands are evaluated left to right before the reflected method is called
    print(token(1) == money(1), token(1) != money(2))
    # in a condition and a comprehension
    if t == m:
        print("equal")
    print([x == m for x in [Token(4), Token(5)]])
    print(len([x for x in [Token(4), Token(5), Token(5)] if x == m]))


main()
