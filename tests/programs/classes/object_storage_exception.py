# an exception as a value of object: printed, and raised once isinstance() narrows it to its class
# (object_exceptions.py)
x: object = ValueError("bad")
print(x, repr(x))


def main() -> None:
    y: object = x
    try:
        if isinstance(y, ValueError):
            raise y
    except ValueError as e:
        print("caught", e)


main()
