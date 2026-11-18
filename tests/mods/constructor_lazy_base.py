class Base:
    def __init__(self, values):
        self.value: int = len(values)

    def get(self) -> int:
        return self.value


Alias = Base


class Unused(Alias):
    def get(self) -> int:
        return self.missing


class ImportedBase:
    def __init__(self, values):
        self.value: int = len(values)

    def get(self) -> int:
        return self.value


class QualifiedBase:
    def __init__(self, values):
        self.value: int = len(values)

    def get(self) -> int:
        return self.value
