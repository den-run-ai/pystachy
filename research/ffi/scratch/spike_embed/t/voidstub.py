def py_fail_void(x: int) -> None: ...
def py_fail_int(x: int) -> int: ...


def main() -> None:
    try:
        py_fail_void(1)
        print("after void")
    except ValueError:
        print("caught void")
    try:
        n = py_fail_int(1)
        print("after int", n)
    except ValueError:
        print("caught int")


main()
