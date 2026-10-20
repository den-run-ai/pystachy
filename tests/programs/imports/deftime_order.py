# Definition time in statement order: see tests/defmods/order.py. Here, object is the builtin
# when the class statement runs (no code has called the function that rebinds it).
print("main: start")
import defmods.order as o


def never() -> None:
    global object
    object = 5


class Local(object):
    def __init__(self) -> None:
        self.v = 1


print(o.total(1), o.first(), Local().v)
