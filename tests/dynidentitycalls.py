# Deliberately no dynamic-any directive: an imported typed function transports identity.
def keep_int(value: int) -> int:
    return value


def keep_float(value: float) -> float:
    alias = value
    return alias


VALUE = float("nan")


def default(value: float = VALUE) -> float:
    return value
