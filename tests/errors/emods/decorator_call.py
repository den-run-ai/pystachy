def reg(name):
    print("reg", name)

    def inner(f):
        return f

    return inner


@reg("x")
def handler(x: int) -> int:
    return x
