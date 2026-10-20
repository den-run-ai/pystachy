# error: 'str' object cannot be interpreted as an integer
def name(none: bool) -> str | None:
    return None if none else "7"


print(oct(name(False)))
