# A nested function's selector: its calls in the enclosing function give it literals.
def outer(n: int) -> None:
    def inner(x: int, boxed=False):
        if boxed:
            return [x + n]
        return x + n

    print(inner(1), inner(2, True), inner(3, boxed=False))


outer(10)
outer(20)
