from typing import ClassVar
class Options:
    PER_MODULE: ClassVar[frozenset[str]] = frozenset({"a", "b"})
print(sorted(Options.PER_MODULE))
