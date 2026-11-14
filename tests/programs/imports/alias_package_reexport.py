# A type alias that a package re-exports from its submodule, imported from the package.
from tcmods.aliaspkg import Row, Tag, pick

first: Row = pick("first")
second: Row = pick("second")
tag: Tag = "second"
print(first, second, pick(tag), tag)


def count(row: Row) -> int:
    if isinstance(row, dict):
        return len(row)
    if isinstance(row, list):
        return len(row) * 10
    return -1


print(count(first), count(second), count("text"), count(None))
