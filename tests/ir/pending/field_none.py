# Bug B (open): a field assigned the result of a function that returns None gets the type
# None, and the compiler prints %C.A = type {void, i64}, which llvm-as rejects.
def setup() -> None:
    print("setup")


class A:
    def __init__(self) -> None:
        self.x = setup()
        self.n = 1


a = A()
print(a.x, a.n)
