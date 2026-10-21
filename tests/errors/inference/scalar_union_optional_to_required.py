# error: argument 1 of required() may be None (int | str | None)

def required(value: int | str) -> int:
    if isinstance(value, int):
        return value
    return len(value)

def unsafe(value: int | str | None) -> int:
    return required(value)

print(unsafe(None))
