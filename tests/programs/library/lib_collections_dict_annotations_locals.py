# A local annotated as a dict whose value is a call of collections' defaultdict, OrderedDict or
# Counter (mypy's checker.py and stubutil.py): it holds that object, whose missing keys call
# the factory
from collections import Counter, OrderedDict, defaultdict
from collections.abc import Mapping
from typing import Dict, MutableMapping


class SymbolNode:
    def __init__(self, name: str) -> None:
        self.name = name


def captures(names: list[str]) -> None:
    nodes = [SymbolNode(n) for n in names]
    all_captures: dict[SymbolNode, list[tuple[str, int]]] = defaultdict(list)
    for i in range(len(names)):
        all_captures[nodes[i % 2]].append((names[i], i))
    for node in nodes[:2]:
        print(node.name, all_captures[node])
    print(len(all_captures[nodes[-1]]), len(all_captures))


def module_paths(entries: list[tuple[str, str]]) -> None:
    module_map: Mapping[str, list[str]] = defaultdict(list)
    for mod, path in entries:
        module_map[mod].append(path)
    print(sorted(module_map.items()), module_map["none"], "none" in module_map)


def others(text: str) -> None:
    counted: Dict[str, int] = Counter(text)
    seen: MutableMapping[str, int] = OrderedDict()
    for ch in text:
        seen[ch] = counted[ch]
    print(counted["a"], counted["?"], list(seen), seen)


def grouped(words: list[str]) -> None:
    groups: dict[int, list[str]] = defaultdict(list)

    def add(w: str) -> None:
        groups[len(w)].append(w)

    for w in words:
        add(w)
    print(sorted(groups.items()), groups[0], len(groups))


captures(["a", "b", "c", "d", "e"])
grouped(["ab", "c", "de", "fgh"])
module_paths([("os", "/a"), ("sys", "/b"), ("os", "/c")])
others("banana")
