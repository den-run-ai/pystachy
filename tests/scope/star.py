# Without __all__, import * takes the public names bound when the module's code ends.
tmp = 5
kept = tmp * 2
del tmp


def setup() -> None:
    global late
    late = 5
