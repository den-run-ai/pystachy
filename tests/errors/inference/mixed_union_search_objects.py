# error: closed union operations require narrowing with isinstance() first
class Entry:
    def __init__(self, value: int) -> None:
        self.value: int = value

def count(values: list[list[Entry] | str], value: list[Entry]) -> int:
    return values.count(value)

print(count([[Entry(1)]], [Entry(1)]))
