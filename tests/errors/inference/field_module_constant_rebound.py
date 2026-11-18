# error: cannot infer the type of field 'cap'
# A module global that statements bind to values of different types is no constant: a field
# stored from it needs an annotation, as the type the global ends up with is not its first value's
LIMIT = 10


class Box:
    def __init__(self) -> None:
        self.cap = LIMIT


LIMIT = "twenty"
print(Box().cap)
