# error: comparing closed union values requires narrowing with isinstance() first
class Entry:
    def __init__(self, value: int) -> None:
        self.value: int = value

def equal(a: list[Entry] | str, b: list[Entry] | str) -> bool:
    return a == b

print(equal([Entry(1)], "entry"))
