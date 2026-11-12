# error: expected int, got str
# A set display types its field by its first item, as a list display does.
class Seen:
    def __init__(self) -> None:
        self.items = {1, "a"}


print(len(Seen().items))
