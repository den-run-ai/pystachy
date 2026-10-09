# error: 'n' is assigned None and int, and None/Optional is only supported for class types, str, list, dict and tuple
def count(xs: list[str]) -> None:
    n = None
    for x in xs:
        n = len(x)
    print(n)


count(["a"])
