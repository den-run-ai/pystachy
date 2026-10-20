# pystachy: dynamic-any
# tomllib from a module that opts in to dynamic Any, as tomllib's own modules do: Any annotations
# hold its values as they are; a parse_float that returns a dict or a list (the Any containers of
# such a module) raises CPython's ValueError (test_error.TestError.test_invalid_parse_float)
import tomllib
from typing import Any, Callable


def dict_returner(s: str) -> Any:
    return {}


def list_returner(s: str) -> Any:
    return []


def check(invalid_parse_float: Callable[[str], Any]) -> None:
    try:
        tomllib.loads("f=0.1", parse_float=invalid_parse_float)
        raise AssertionError("no ValueError")
    except ValueError as e:
        print("ValueError:", e)


check(dict_returner)
check(list_returner)


def walk(v: Any, depth: int) -> None:
    # (every value of a document, by its type)
    if isinstance(v, dict):
        for k in v:
            print("  " * depth + str(k) + ":")
            walk(v[k], depth + 1)
    elif isinstance(v, list):
        for x in v:
            walk(x, depth + 1)
    else:
        print("  " * depth + type(v).__name__, repr(v))


doc: Any = tomllib.loads("""
name = "x"
values = [1, 2.5, "three", true, 1979-05-27]
[table]
nested = { a = [{ b = 1 }] }
""")
walk(doc, 0)
total: Any = 0
for v in doc["values"]:
    if isinstance(v, int) or isinstance(v, float):
        total = total + v
print(total, doc["table"]["nested"]["a"][0]["b"] + 1)
