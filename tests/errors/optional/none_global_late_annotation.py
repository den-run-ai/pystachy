# error: 'value' was declared as int | None, not str | None
# A provisional read needs replay, but its inferred hint cannot override a later declaration.
value = None


def set_value(v):
    global value
    value = v


def is_none():
    return value is None


print(is_none())
set_value(5)
value: str | None = None
