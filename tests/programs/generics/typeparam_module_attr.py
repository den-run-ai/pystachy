# A type parameter is not another module's attribute of the same name: token.OP and token.NL
# are token's ints in a generic function and a generic class whose parameters are named OP
# and NL.
import token


def first[OP](xs: list[OP]) -> OP:
    print(token.OP)
    return xs[0]


class Box[NL]:
    def __init__(self, v: NL) -> None:
        self.v = v

    def get(self) -> NL:
        print(token.NL)
        return self.v


print(first([1, 2]), first(["a"]))
print(Box(2.5).get())
