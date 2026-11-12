# error: cannot infer the type of field 'value'; annotate it (self.value: T = ...)
class Box:
    def __init__(self, n: int | None, s: str) -> None:
        self.value = n or s


print(Box(None, "x").value)
