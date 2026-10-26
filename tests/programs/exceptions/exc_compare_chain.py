# A chained comparison of exception classes' objects where one link always raises TypeError (the
# hierarchy defines __eq__ but no ordering): the chain runs __eq__ first, then raises where the
# ordering runs, and is false without reaching it where __eq__ is false. (#908: the chain did not
# compile, as for ordinary classes.)
class E(Exception):
    def __init__(self, k: int) -> None:
        self.k = k

    def __eq__(self, other: "E") -> bool:
        print("eq", self.k, other.k)
        return self.k == other.k


class F(E):
    pass


def f(x: E, y: E, z: E) -> bool:
    return x == y < z


try:
    print(f(F(1), F(1), F(2)))
except TypeError as e:
    print("TypeError:", e)
print(f(F(1), E(2), F(3)))
