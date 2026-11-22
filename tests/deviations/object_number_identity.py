# Documented deviation: 'is' between values of object that hold numbers compares their types and
# values (a float's bits), as PyPy does. Equal numbers computed apart are two objects in CPython,
# which gives False below; small ints, bools and a module's equal constants are one object in both.
def computed(k: int) -> object:
    return k * 1000 + 7


def tenth(k: int) -> object:
    return k * 0.1


def main() -> None:
    x = computed(3)
    y = computed(3)
    a = tenth(3)
    b = tenth(3)
    print(x is y, x == y, a is b, a == b)


main()
