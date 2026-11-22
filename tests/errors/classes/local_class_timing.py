# error: local_class_timing.py:7: error: a class inside a function is not supported: its statement reads LIMIT, which the module may bind or change while the function runs
# CPython reads LIMIT where the class statement runs, after setup() binds it: Pystachy would make
# the class earlier, before the module statement that runs main()
def main() -> None:
    setup()

    class C:
        x = LIMIT

    print(C.x)


def setup() -> None:
    global LIMIT
    LIMIT = 5


main()
