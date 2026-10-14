def retain(value, unused=None):
    return value


def optional(value, count: int | None = 7):
    return count


def nested(value):
    return retain(value)
