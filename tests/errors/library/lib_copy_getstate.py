# error: copy.copy() of a Counter object is not supported: its class defines __getstate__, by which CPython's copy would copy it
# CPython copies the object through the pickling protocol: __getstate__() and __setstate__() (printing 2)
import copy


class Counter:
    def __init__(self, v: int) -> None:
        self.v = v

    def __getstate__(self) -> dict[str, int]:
        return {"v": self.v + 1}

    def __setstate__(self, state: dict[str, int]) -> None:
        self.v = state["v"]


print(copy.copy(Counter(1)).v)
