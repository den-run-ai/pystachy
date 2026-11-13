# error: cannot infer the type of field 'items'; annotate it (self.items: T = ...)
# A set display types its field only where all its items have one type.
class Seen:
    def __init__(self) -> None:
        self.items = {1, "a"}


print(len(Seen().items))
