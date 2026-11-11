from collections.abc import Sequence
class Type:
    def name(self) -> str:
        return "type"
class Instance(Type):
    def name(self) -> str:
        return "instance"
def names(ts: Sequence[Type]) -> list[str]:
    return [t.name() for t in ts]
insts: list[Instance] = [Instance(), Instance()]
print(names(insts))
