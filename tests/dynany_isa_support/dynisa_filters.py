# pystachy: dynamic-any
# The helper of tests/programs/inference/dynany_isinstance_late_subclass.py, shaped as logging's
# filters: the isinstance() test of each Any filter in Filterer.filter() is compiled by the
# program's first log() call, before the program boxes an object of a subclass of Filter that it
# defines after that call
from typing import Any


class Record:
    def __init__(self, msg: Any) -> None:
        self.msg: Any = msg


class Filter:
    def __init__(self, name: str = "") -> None:
        self.name = name

    def filter(self, record):
        return True


class Filterer:
    def __init__(self) -> None:
        self.filters: list[Any] = []

    def addFilter(self, filter):
        self.filters.append(filter)

    def filter(self, record) -> Any:
        for f in self.filters:
            if isinstance(f, Filter):
                result = f.filter(record)
            else:
                result = f(record)
            if not result:
                return False
        return record


class Logger(Filterer):
    def __init__(self) -> None:
        Filterer.__init__(self)

    def log(self, msg: Any) -> None:
        r = Record(msg)
        if self.filter(r):
            print("emit", r.msg)
