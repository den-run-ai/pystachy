# Constructor fields keep the concrete return type of a generic helper.
# Inferring that type must not execute the helper or duplicate default values.
from io import StringIO


calls = 0


def default_label() -> str:
    print("default")
    return "implicit"


def retain(value, label: str = default_label()):
    global calls
    calls += 1
    print("retain", label, calls)
    return value


class Holder:
    def __init__(self, value) -> None:
        self.original = retain(value)
        self.alias = retain(value, "explicit")


class Token:
    def __init__(self, value: int) -> None:
        self.value = value


stream = StringIO("abcdef")
memory = Holder(stream)
print(memory.original is stream, memory.alias is stream)
print(memory.original.read(1), memory.alias.read(2), stream.read(1))
token = Token(7)
object_holder = Holder(token)
print(object_holder.original is token, object_holder.alias is token)
object_holder.alias.value += 3
print(token.value, object_holder.original.value)
print("calls", calls)
stream.close()
