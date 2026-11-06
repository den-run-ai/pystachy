# pystachy: dynamic-any
# flatten a nested document into dotted keys (flatten-dict style)
from typing import Any


def flatten(x: Any, prefix: str, out: dict[str, Any]) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            flatten(v, prefix + "." + k if prefix else k, out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            flatten(v, prefix + "." + str(i), out)
    else:
        out[prefix] = x


out: dict[str, Any] = {}
flatten({"a": {"b": 1, "c": [2, "x", {"d": None}]}, "e": 2.5}, "", out)
print(out)
