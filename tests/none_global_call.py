# A module global given only a call's None (setup() is declared -> None) reads as None: its one
# binding, compiled before the read, gave it a value of type None, as for a local.
def setup() -> None:
    pass


x = setup()
print(x)


def show() -> None:
    print(x is None)


show()
