# Optional caught exceptions keep the identity of their original user object.
class Child(ValueError):
    pass


class Holder:
    def __init__(self) -> None:
        self.error: BaseException | None = None


def child_identity(value: BaseException | None, original: Child) -> None:
    print(value is original, original is value)
    print(value is not original, original is not value)


def builtin_identity(value: BaseException | None, original: BaseException) -> None:
    print(value is original, original is value)
    print(value is not original, original is not value)


def optional_identity(left: BaseException | None, right: BaseException | None) -> None:
    print(left is right, right is left, left is not right, right is not left)


original = Child("message")
different = Child("message")
holder = Holder()
second = Holder()
empty = Holder()
child_identity(holder.error, original)
optional_identity(holder.error, second.error)
try:
    raise original
except BaseException as caught:
    holder.error = caught
try:
    raise original
except BaseException as caught:
    second.error = caught

# Direct fields and a narrowed local both need canonical exception identity.
print(holder.error is original, original is holder.error)
print(holder.error is not original, original is not holder.error)
local = holder.error
child_identity(local, original)
if local is not None:
    print(local is original, original is local)
child_identity(holder.error, different)
optional_identity(holder.error, second.error)
optional_identity(holder.error, empty.error)
optional_identity(empty.error, second.error)

try:
    raise different
except BaseException as caught:
    second.error = caught
optional_identity(holder.error, second.error)

builtin = ValueError("builtin")
other_builtin = ValueError("builtin")
builtin_identity(empty.error, builtin)
try:
    raise builtin
except BaseException as caught:
    holder.error = caught
try:
    raise builtin
except BaseException as caught:
    second.error = caught
builtin_identity(holder.error, builtin)
builtin_identity(holder.error, other_builtin)
child_identity(holder.error, original)
optional_identity(holder.error, second.error)
print(holder.error is None, None is holder.error)
print(empty.error is None, None is empty.error)
holder.error = None
optional_identity(holder.error, second.error)
optional_identity(holder.error, empty.error)
