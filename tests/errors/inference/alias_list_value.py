# error: list[...] as a value is not supported (only annotations may name a type
# A module-level Row = list[str] is a type alias; a function's local is a value, as here.
def rows():
    Row = list[str]
    return Row


print(rows())
