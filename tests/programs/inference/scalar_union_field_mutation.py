# A call may change the field: the read after it is the union's, whose str has no + with an int.
class Event:
    def __init__(self, value: int | str) -> None:
        self.value = value

def change(event: Event) -> None:
    event.value = "changed"

def unsafe(event: Event) -> int:
    if isinstance(event.value, int):
        change(event)
        return event.value + 1
    return 0

print(unsafe(Event(1)))
