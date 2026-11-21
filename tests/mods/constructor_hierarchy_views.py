from typing import Any


class Label:
    # A fixed layout whose constructor takes any value. LoudLabel is declared, not always used.
    def __init__(self, value: Any) -> None:
        self.text: str = str(value)

    def shown(self) -> str:
        return "<" + self.text + ">"


class LoudLabel(Label):
    def shown(self) -> str:
        return self.text.upper()


class View:
    # A hierarchy of its own whose constructor takes a Label.
    def __init__(self, label: "Label") -> None:
        self.name: str = label.shown()

    def describe(self) -> str:
        return "view " + self.name


class WideView(View):
    def describe(self) -> str:
        return "wide " + self.name
