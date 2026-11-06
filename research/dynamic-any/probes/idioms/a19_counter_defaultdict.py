# pystachy: dynamic-any
# collections.Counter and defaultdict over mixed records
from collections import Counter, defaultdict
from typing import Any

events: list[Any] = [{"k": "a", "v": 1}, {"k": "b", "v": 2.5}, {"k": "a", "v": "x"}]
c = Counter(e["k"] for e in events)
print(c.most_common())
g: defaultdict[str, list[Any]] = defaultdict(list)
for e in events:
    g[e["k"]].append(e["v"])
print(dict(g))
