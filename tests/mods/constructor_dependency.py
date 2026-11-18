from collections import Counter, defaultdict
from typing import Iterable


class Options:
    def __init__(self, strict: bool) -> None:
        self.strict: bool = strict
        self.flags: Counter[str] = Counter()
        self.flags["strict"] += 1 if strict else 0


class Errors:
    def __init__(self) -> None:
        self.items: defaultdict[str, set[str]] = defaultdict(set)

    def count(self) -> int:
        return len(self.items)


class Root:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = sum(values)

    def read(self) -> int:
        return self.value


class Child(Root):
    def __init__(self, errors: Errors) -> None:
        self.errors: Errors = errors
        self.value: int = errors.count()


# Eagerly preparing every descendant would admit this dependency or fail on its
# invalid constructor/override. An import and a use of Child do neither.
class UnusedErrors:
    def __init__(self) -> None:
        self.items: defaultdict[str, set[str]] = defaultdict(set)
        self.invalid = missing_name


class UnusedChild(Root):
    def __init__(self, errors: UnusedErrors) -> None:
        self.errors: UnusedErrors = errors
        self.value: int = 0

    def read(self) -> int:
        return missing_name


class NestedErrors:
    def __init__(self, options: Options) -> None:
        self.options: Options = options
        self.items: defaultdict[str, set[str]] = defaultdict(set)

    def count(self) -> int:
        return len(self.items)


class NestedChild(Root):
    def __init__(self, errors: NestedErrors) -> None:
        self.errors: NestedErrors = errors
        self.value: int = errors.count()


class Variable:
    def __init__(self, item):
        self.item = item


class Extracted(Root):
    def __init__(self, source: Variable) -> None:
        self.value: int = int(source.item)
