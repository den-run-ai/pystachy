# A frozenset key whose elements' __eq__ runs where two frozensets compare: what it raises reaches
# the handler around the lookup, also in a set and through nested frozensets, and a KeyError's
# message runs the elements' __repr__.
class Bad:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: object) -> bool:
        raise ValueError(f"eq {self.v}")

    def __hash__(self) -> int:
        return 1


class Shown:
    def __init__(self, v: int) -> None:
        self.v = v

    def __repr__(self) -> str:
        return f"Shown({self.v})"


a = frozenset([Bad(1)])
b = frozenset([Bad(2)])
try:
    print(b in {a: 1})
except ValueError as e:
    print("ValueError", e)
s = {a}
try:
    print(b in s)
except ValueError as e:
    print("ValueError", e)
nested = {frozenset([a]): 1}
try:
    print(frozenset([b]) in nested)
except ValueError as e:
    print("ValueError", e)
shown = {frozenset([Shown(1)]): 1}
try:
    print(shown[frozenset([Shown(2)])])
except KeyError as e:
    print("KeyError", e)
