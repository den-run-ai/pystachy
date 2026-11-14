from __future__ import annotations

from tcpkg.rtypes import RInstance


class FuncIR:
    def __init__(self, name: str) -> None:
        self.name = name


class ClassIR:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attrs: dict[str, str] = {"x": "int"}

    def attr_type(self, attr: str) -> str:
        return self.attrs.get(attr, "object")

    def instance(self) -> RInstance:
        return RInstance(self)
