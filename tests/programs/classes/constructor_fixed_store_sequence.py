class Later:
    def __init__(self, value):
        self.value = value
        self.value: int = value + 1


class Earlier:
    def __init__(self, value):
        self.value: int = value
        self.value = value + 1


class Declared:
    value: int

    def __init__(self, value):
        if isinstance(value, int):
            self.value = value
        else:
            self.value = len(value)


print(Later(3).value, Earlier(3).value)
print(Declared(3).value, Declared("hello").value)
