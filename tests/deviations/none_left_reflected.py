# Documented deviation: a left operand that is None when it runs raises CPython's TypeError for
# None, also where the right operand's class defines the reflected method. CPython calls it with
# None instead: B.__ror__ and V.__rxor__ here (it prints "ror" and "rxor").
class A:
    def __or__(self, o: "B") -> str:
        return "or"


class B:
    def __ror__(self, o: A) -> str:
        return "ror"


class V:
    def __xor__(self, o: "V") -> str:
        return "xor"

    def __rxor__(self, o: "V") -> str:
        return "rxor"


def a(k: int) -> A | None:
    return A() if k > 0 else None


def v(k: int) -> V | None:
    return V() if k > 0 else None


for k in [1, 0]:
    try:
        print(a(k) | B())
    except TypeError as e:
        print("TypeError:", e)
    try:
        print(v(k) ^ V())
    except TypeError as e:
        print("TypeError:", e)
