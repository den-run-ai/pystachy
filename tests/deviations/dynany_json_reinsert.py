# pystachy: dynamic-any
# Documented deviation: json.dumps() of Any values (lib/_pystachy_json_any.py) writes a dict's
# entries in the order they had where it started, with the values they have when reached, the
# keys that a default() callback adds after the others and without those it deletes, as CPython
# does. A key that a callback deletes and inserts again is written in its old place, where
# CPython, walking the dict's table, writes it after the others: here {"a": 1, "b": 0, "c": 4}
# where CPython writes {"a": 1, "c": 4, "b": 0}. Following it would take the dict's table, which
# library code cannot walk (#823).
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
