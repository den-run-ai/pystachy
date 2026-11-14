import typevalues


def marked(value):
    print("effect")
    return value


def right(value):
    return type(marked(value)) is Box


def left(value):
    return Box is type(marked(value))


try:
    right(typevalues.value())
except NameError:
    print("right unbound")
try:
    left(typevalues.value())
except NameError:
    print("left unbound")


class Box:
    def __init__(self, value):
        self.value = value


print(right(typevalues.value()), left(typevalues.value()))
