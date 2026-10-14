"""Narrow copied values, forget reassigned loop variables, and keep guard exits."""
value: int | str = 2

class Event:
    def __init__(self, value: int | str) -> None:
        self.value = value

def mutate_global() -> None:
    global value
    value = "changed"

def copied_global() -> int:
    local = value
    if isinstance(local, int):
        mutate_global()
        return local + 3
    return len(local)

def copied_field(event: Event) -> str:
    local = event.value
    if isinstance(local, str):
        event.value = 123
        return local.upper()
    return str(local)

def loop(value: int | str, count: int) -> int:
    result = 0
    for i in range(count):
        if isinstance(value, int):
            result += value
            value = "abc"
        else:
            result += len(value)
            value = i
    return result

def guard(value: int | str | None) -> int:
    if value is None:
        return -1
    if isinstance(value, str):
        return len(value)
    return value + 1

def joined(flag: bool, value: int | str) -> int:
    if flag:
        if not isinstance(value, str):
            return 1
    else:
        if isinstance(value, int):
            return 2
    return len(value)

def loop_break(value: int | str) -> int:
    while isinstance(value, str):
        value = len(value)
        break
    return value + 1

print(copied_global(), copied_global())
print(copied_field(Event("hello")), copied_field(Event(3)))
print(loop(4, 5), loop("four", 4))
print(guard(None), guard("word"), guard(5))
print(joined(True, "abc"), joined(False, "abcd"))
print(joined(True, 2), joined(False, 2))
print(loop_break("abcd"), loop_break(3))
