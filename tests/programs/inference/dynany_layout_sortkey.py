# pystachy: dynamic-any
# A sort's keys are a list too: keys that are Any containers are compared as boxes, as the list of
# them holds them (#821).
from typing import Any


def tags(r: dict[str, Any]) -> list[Any]:
    return [r["n"], r["s"]]


recs: list[dict[str, Any]] = [{"n": 2, "s": "b"}, {"n": 1, "s": "a"}, {"n": 2, "s": "a"}]
print(sorted(recs, key=tags))
print(sorted(recs, key=tags, reverse=True)[0])
print(min(recs, key=tags), max(recs, key=tags))
recs.sort(key=tags)
print(recs)
