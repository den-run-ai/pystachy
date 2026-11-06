# pystachy: dynamic-any
from typing import Any


class ImportedRecord:
    def __init__(self, data: list[Any], label: str = "imported") -> None:
        self.data = data
        self.label = label
