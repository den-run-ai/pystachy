"""A class that only *args or **kwargs of a hierarchy's __init__ name stays a class template.

Errors is such a class. Nothing makes one, so it is never compiled, and its field that nothing
types is no error: only a class that would make the hierarchy's class a template is compiled as
an ordinary class (inheritance_template_param.py).
"""

from collections import defaultdict


class Errors:
    def __init__(self) -> None:
        self.seen: defaultdict[str, set[str]] = defaultdict(set)
        self.rest = []


class Node:
    def name(self) -> str:
        return "node"


class Star(Node):
    def __init__(self, *errors: Errors) -> None:
        self.count = len(errors)

    def name(self) -> str:
        return "star"


class Named(Node):
    def __init__(self, **errors: Errors) -> None:
        self.count = len(errors)

    def name(self) -> str:
        return "named"


def main() -> None:
    nodes: list[Node] = [Node(), Star(), Named()]
    for n in nodes:
        print(n.name())
    print(Star().count, Named().count)


main()
