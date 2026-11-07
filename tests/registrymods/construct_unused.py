# pystachy: dynamic-any
# Merely importing a class and storing it must not compile its unused body.
class Unused:
    def __init__(self, value: int) -> None:
        eval("value + 1")
