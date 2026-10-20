# A global given only a call's None (see none_global_module.py).
def setup() -> None:
    pass


x = setup()


def show() -> None:
    print(x)
