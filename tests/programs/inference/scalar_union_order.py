"""Dispatch does not duplicate calls, reorder operands or suppress exceptions."""
events: list[str] = []

def value(label: str, v: int | str | None) -> int | str | None:
    events.append(label)
    return v

print(value("left", 1) == value("right", "1"))
print(events)
events.clear()
print(value("false", "") or value("fallback", "text"))
print(value("true", 7) or value("skipped", 8))
print(value("and", 0) and value("skipped", 9))
print(events)
events.clear()
print(str(value("str", "text")), repr(value("repr", "text")), bool(value("bool", 0)))
print(events)
events.clear()

def fail() -> int | str | None:
    events.append("fail")
    raise ValueError("query failed")

def receiver() -> list[int | str | None]:
    events.append("receiver")
    return [1, "text"]

try:
    print(value("before", 1) == fail())
except ValueError as error:
    print(str(error))
print(events)
events.clear()
try:
    print(receiver().index(fail()))
except ValueError as error:
    print(str(error))
print(events)
events.clear()
try:
    print(fail() in receiver())
except ValueError as error:
    print(str(error))
print(events)
