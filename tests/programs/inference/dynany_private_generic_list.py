# pystachy: dynamic-any
# Private generic members and recursive specialization retain a native list alias.
from typing import Any

from stack_items import Store


def run() -> None:
    first: Store[str] = Store("first", [int("1000"), int("1001")])
    second: Store[str] = Store("second", [2])
    first.link(second)
    print("names", first.name(), first.next_name())
    print("reflection", hasattr(first, "__items"), hasattr(first, "_Store__items"))
    native = first.items()
    view: Any = native
    item = native[0]
    print("identity", view is native, view[0] is item)
    view.append(3)
    native.insert(0, 4)
    view[1:2] = [5, 6]
    print("mutations", native, view)
    print("sums", sum(native), sum(view), sum(view, 0.5))
    copy: Any = view.copy()
    copy.append("free")
    print("copy", copy, native)
    for i in range(30):
        garbage: Any = [str(i), {"items": [i, i + 1]}]
        assert len(garbage) == 2
    print("retained", view is first.items(), first.next_name(), view)


run()
