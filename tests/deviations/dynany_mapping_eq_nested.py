# pystachy: dynamic-any
# Remaining #803 gap: a mapping whose values are typed containers, compared with a dict held as
# an Any value. No comparison pairs a typed list with an Any value (a module that opts in also
# rejects dict[str, list[int]] == dict[Any, Any]), so this one raises the explicit
# unsupported-comparison TypeError, where CPython prints True
from collections import defaultdict
from typing import Any

groups: defaultdict[str, list[int]] = defaultdict(list)
groups["a"].append(1)
held: Any = groups
plain: Any = {"a": [1]}
print(held == plain)
