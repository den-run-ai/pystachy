# raise ... from c of a class object that may be None, in a program that never reads __cause__:
# a class is still called (its __init__ runs), None is not


class Noisy(Exception):
    def __init__(self) -> None:
        super().__init__("noisy")
        print("made Noisy")


def quiet(c: type[BaseException] | None) -> None:
    try:
        raise ValueError("q") from c
    except ValueError as e:
        print("caught", e)


quiet(None)
quiet(Noisy)
