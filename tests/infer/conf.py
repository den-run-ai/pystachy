# Module globals that only this module's functions assign.
def setup() -> None:
    global late
    late = 5


def setup_names() -> None:
    global names
    names = ["a", "b"]


def get() -> int:
    return late
