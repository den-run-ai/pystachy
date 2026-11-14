# error: runtime-length tuple elements must be int, float, bool, str or their optional types, or objects of one of the program's classes (not an exception, a NamedTuple or a union of classes)
# Objects of a union of classes are not such items yet: a tuple slot holds the union's box, whose
# tag the narrowing of an item read from the slot cannot prove yet
class Capsule:
    def __init__(self, name: str) -> None:
        self.name = name


class SourceDep:
    def __init__(self, path: str) -> None:
        self.path = path


deps: tuple[Capsule | SourceDep, ...] = (Capsule("a"), SourceDep("b.c"))
print(len(deps))
