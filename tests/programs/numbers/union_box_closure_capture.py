# A closure's int | float local given a captured int boxes it with the int's tag (#1551): the IR
# check (PYSTACHY_IRCHECK=1) proves the box's tag and payload from the capture.
def outer(k: int) -> str:
    def inner() -> str:
        v: int | float = k
        return str(v)
    return inner()


def either(k: int, f: float) -> str:
    def inner(flag: bool) -> str:
        v: int | float = f
        if flag:
            v = k
        return str(v)
    return inner(True) + " " + inner(False)


print(outer(3))
print(either(2, 2.5))
