# error: field_global_item_rebound.py:15: error: cannot infer the type of field 'count'; annotate it (self.count: T = ...)
# A field stored from an item of a module global types only by the global's annotation where
# that annotated assignment is the global's one binding: here a function binds it too.
COUNTS: dict[str, int] = {"a": 1}


def reset() -> None:
    global COUNTS
    COUNTS = {}


class Box:
    def __init__(self) -> None:
        self.label = "box"
        self.count = COUNTS["a"]


print(Box().count)
