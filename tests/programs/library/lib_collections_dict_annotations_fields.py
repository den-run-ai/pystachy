# A field annotated as a dict whose value is a call of collections' defaultdict, OrderedDict or
# Counter: it holds that object, whose missing keys call the factory in each method
from collections import Counter, OrderedDict, defaultdict
from collections.abc import Mapping
from typing import Dict, MutableMapping


class Index:
    def __init__(self) -> None:
        self.by_key: dict[str, list[int]] = defaultdict(list)
        self.hits: Mapping[str, int] = Counter()
        self.order: MutableMapping[str, int] = OrderedDict()
        self.width: Dict[str, int] = defaultdict(lambda: 1)

    def add(self, key: str, value: int) -> None:
        self.by_key[key].append(value)
        self.order[key] = value

    def report(self) -> None:
        print(self.by_key, self.by_key["absent"], len(self.by_key))
        print(self.hits["x"], len(self.hits), list(self.order), self.width["w"], len(self.width))


ix = Index()
ix.add("b", 2)
ix.add("a", 1)
ix.add("b", 3)
ix.report()
print(isinstance(ix.by_key, dict), type(ix.hits).__name__, type(ix.order).__name__)
