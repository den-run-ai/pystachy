# pystachy: dynamic-any
# The reducer's class has no typed construction or original boxed instance.
from typing import Any
from registrymods import copyreg_slice as copyreg


class Source:
    def __init__(self, data: list[Any], label: str) -> None:
        self.data = data
        self.label = label


class Restored:
    def __init__(self, data: list[Any], label: str) -> None:
        self.data = data
        self.label = label


def reduce_source(value: Any) -> Any:
    return (Restored, (value.data, value.label))


def restore(value: Any) -> Any:
    reducer = copyreg.dispatch_table[type(value)]
    factory, arguments = reducer(value)
    return factory(*arguments)


copyreg.pickle(Source, reduce_source, Restored)
shared: list[Any] = [7, "state"]
source: Any = Source(shared, "source")
copied = restore(source)
again = restore(source)
print(type(copied) is Restored, copied is source, copied is again)
print(copied.label, copied.data is source.data, again.data is shared)
copied.data.append("shared")
print(source.data, again.data)
