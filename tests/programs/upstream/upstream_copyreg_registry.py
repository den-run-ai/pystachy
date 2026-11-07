# pystachy: dynamic-any
# Exercise CPython's selected copyreg registration functions, not pickle itself.
from typing import Any
from registrymods import copyreg_slice as copyreg


class Event:
    def __init__(self, code: int, label: str):
        self.code = code
        self.label = label


class SpecialEvent(Event):
    pass


def reduce_event(value: Any) -> Any:
    return (restore_event, ((value.code, value.label),))


def reduce_int(value: Any) -> Any:
    return (restore_value, (value,))


def reduce_str(value: Any) -> Any:
    return (restore_value, (value,))


def reduce_none(value: Any) -> Any:
    return (restore_value, (value,))


def restore_event(state: Any) -> Any:
    return Event(state[0], state[1])


def restore_value(state: Any) -> Any:
    return state


copyreg.pickle(Event, reduce_event, restore_event)
copyreg.pickle(int, reduce_int)
copyreg.pickle(str, reduce_str)
copyreg.pickle(type(None), reduce_none)

values: list[Any] = [Event(7, "boot"), 42, "ready", None]
for value in values:
    reducer = copyreg.dispatch_table[type(value)]
    factory, arguments = reducer(value)
    # A real reduction tuple, with a bounded one-argument reconstruction step.
    # General runtime-sized argument unpacking is a separate feature gap.
    restored = factory(arguments[0])
    print(type(restored) is type(value))
    if isinstance(restored, Event):
        print(restored.code, restored.label, restored is value)
    else:
        print(restored)

# The table dispatches on exact type, including bool versus int and subclasses.
print(type(True) in copyreg.dispatch_table)
print(type(SpecialEvent(9, "special")) in copyreg.dispatch_table)
print(copyreg.dispatch_table[Event] is reduce_event)

# Failed registrations retain CPython's validation and assignment order.
try:
    copyreg.pickle(Event, 0)
except TypeError as exc:
    print(str(exc))
print(copyreg.dispatch_table[Event] is reduce_event)
try:
    copyreg.pickle(Event, reduce_event, 0)
except TypeError as exc:
    print(str(exc))
print(copyreg.dispatch_table[Event] is reduce_event)

# Replacement through the registration parameter must retain the new callback.
copyreg.pickle(int, reduce_str)
print(copyreg.dispatch_table[type(42)] is reduce_str)
print(len(copyreg.dispatch_table))
