# error: 'is' is only supported for objects and None
def same(a: int | None, b: int | None) -> bool:
    return a is b
