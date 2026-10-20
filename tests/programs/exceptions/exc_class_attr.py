# The class an __exit__ takes has CPython's __qualname__; the exception goes on, as nothing suppresses it
from types import TracebackType


class Show:
    def __enter__(self) -> None:
        pass

    def __exit__(self, et: type[BaseException] | None, ev: BaseException | None, tb: TracebackType | None) -> None:
        if et is not None:
            print(et.__qualname__)


with Show():
    raise KeyError("k")
