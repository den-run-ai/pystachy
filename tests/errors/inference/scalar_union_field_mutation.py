# error: closed union arithmetic requires narrowing with isinstance() first
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
