# pystachy: dynamic-any
# Documented deviation: without sort_keys, json.dumps() of Any values keeps queued keys in
# their old order and appends newly observed keys after default() callbacks. CPython walks the
# live dict table, so delete/reinsert and clear/repopulate can change output order or entries.
# CPython 3.13.16 prints these three lines:
# {"a": 1, "c": 4, "b": 0}
# {"a": 1}
# {"a": 1, "y": 8}
# Pystachy's intended deviation is recorded in the hand-written .out: the reinserted key keeps
# its old place, and all replacement keys are emitted. Exact live table traversal is not
# exposed to library code (#823).
import json
from typing import Any


class Later:
    pass


doc: dict[str, Any] = {"a": Later(), "b": 0, "c": 4}


def move(o: Any) -> Any:
    del doc["b"]
    doc["b"] = 0
    return 1


print(json.dumps(doc, default=move))


one: dict[str, Any] = {"a": Later(), "b": 2}


def replace_one(o: Any) -> Any:
    one.clear()
    one["z"] = 9
    return 1


two: dict[str, Any] = {"a": Later(), "b": 2}


def replace_two(o: Any) -> Any:
    two.clear()
    two["z"] = 9
    two["y"] = 8
    return 1


print(json.dumps(one, default=replace_one))
print(json.dumps(two, default=replace_two))
