# xs[a:b] op= v asks an object bound for its __index__() again at the store, after the right
# operand has run, as CPython's read and store each convert the bounds.
class Seq:
    def __init__(self) -> None:
        self.n = 0

    def __index__(self) -> int:
        self.n += 1
        print("index", self.n)
        return self.n


def rhs() -> list[int]:
    print("rhs")
    return [9]


x = Seq()
xs = [0, 1, 2, 3]
xs[x:] += rhs()
print(xs)
y = Seq()
ys = [0, 1, 2, 3, 4, 5]
ys[y:y] *= 2
print(ys)
