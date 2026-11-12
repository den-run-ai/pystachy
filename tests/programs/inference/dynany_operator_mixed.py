# pystachy: dynamic-any
from typing import Any

events: list[str] = []


class Left:
    def __eq__(self, other):
        events.append("left eq")
        return True

    def __lt__(self, other):
        events.append("left lt")
        return True


class Right:
    def __eq__(self, other):
        events.append("right eq")
        return False

    def __gt__(self, other):
        events.append("right gt")
        return False


left: Any = Left()
right = Right()
print(left == right, right == left)
print(left != right, right != left)
print(left < right, right > left)
print(events)


class Target:
    pass


class Reflected:
    def __radd__(self, other: Any) -> Target:
        events.append("reflected add")
        return Target()


def source() -> Any:
    events.append("source")
    return Reflected()


events.clear()
target: Target = Target()
target += source()
print(type(target).__name__, events)


class Inplace:
    def __iadd__(self, other: Any) -> "Inplace":
        events.append("inplace add")
        return self


events.clear()
inplace = Inplace()
original = inplace
inplace += source()
print(inplace is original, events)
