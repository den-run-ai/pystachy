# An __init__ that stores an object of a class template (defaultdict, Counter, deque, ...) into a
# field whose class annotation, or the store's own, is a type of its own does not make its class
# a template: the field takes the object as that type, as a store by another method does, so
# the class can take part in inheritance (mypy's MypyFile stores defaultdict(set) so).
from collections import Counter, OrderedDict, defaultdict, deque


class Node:
    def kind(self) -> str:
        return "node"


class File(Node):
    deps: defaultdict[str, set[str]]
    counts: Counter[str]
    queue: deque[int]
    order: "OrderedDict[str, int]"

    def __init__(self, name: str) -> None:
        self.name = name
        self.deps = defaultdict(set)
        self.counts = Counter()
        self.queue = deque()
        self.order = OrderedDict()
        self.extra: defaultdict[str, list[int]] = defaultdict(list)

    def kind(self) -> str:
        return "file"

    def add(self, mod: str, dep: str) -> None:
        self.deps[mod].add(dep)
        self.counts[mod] += 1
        self.queue.append(len(self.queue))
        self.order[mod] = self.counts[mod]
        self.extra[dep].append(self.counts[mod])


class Stub(File):
    def kind(self) -> str:
        return "stub"


def show(f: File) -> None:
    f.add("m", "x")
    f.add("m", "y")
    f.add("n", "x")
    print(f.kind(), f.name, sorted(f.deps["m"]), f.counts["m"], list(f.queue), list(f.order.items()), f.extra["x"])


show(File("a.py"))
show(Stub("b.pyi"))
nodes: list[Node] = [File("c.py"), Stub("d.pyi"), Node()]
print([n.kind() for n in nodes])
