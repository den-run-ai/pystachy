# pystachy: dynamic-any
# Static construction must not make unused instance helpers/defaults mandatory.
class ColdRepr:
    def __init__(self, value: int) -> None:
        self.value = value

    def __repr__(self) -> str:
        return eval("'unused repr'")


class ColdHash:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return eval("17")


class Marker:
    pass


class ImportedDefault:
    def __init__(self, value: int = Marker) -> None:
        self.value = value
