from collections.abc import Sequence, Iterable, Mapping
class Type:
    def name(self) -> str:
        return "type"
def names(ts: Sequence[Type]) -> list[str]:
    return [t.name() for t in ts]
def count(ts: Iterable[Type]) -> int:
    return len([t for t in ts])
def keys(m: Mapping[str, Type]) -> list[str]:
    return sorted(m)
ts: list[Type] = [Type()]
print(names(ts), count(ts), keys({"a": Type()}))
