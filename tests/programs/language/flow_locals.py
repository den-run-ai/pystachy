from builtins import list as empty_list
import builtins

def parse_count(text):
    value = text.strip()
    value = int(value)
    return value + 1

def rebind_parameter(value):
    value = str(value)
    value = int(value)
    return value + 2

def mean(xs: list[int]) -> float:
    total = 0
    for x in xs:
        total += x
    total = total / len(xs)
    return total

def branches(flag: bool) -> float:
    value = 2
    if flag:
        value = 4
    else:
        value = 6
    value = value / 2
    return value

def aliases() -> str:
    value = "9"
    old = value
    value = int(value)
    previous = value
    value = str(value + 1)
    return old + ":" + str(previous) + ":" + value

class Match:
    def __init__(self, text: str) -> None:
        self.text = text
    def group(self, index: int) -> str:
        return self.text

def replace(s):
    s = s.group(1)
    if s[0] == "#":
        return int(s[1:])
    return 0

print(parse_count(" 41 "))
print(rebind_parameter("20"), rebind_parameter(20))
print(mean([1, 2, 3, 4]), mean([3]))
print(branches(True), branches(False))
print(aliases())
print(replace(Match("#123")), replace(Match("abc")))

# A version established outside a block is also used by its stores and loads.
def after_rebinding(flag: bool) -> str:
    value = 10
    value = str(value)
    if flag:
        value = value + "!"
    for i in range(2):
        value += str(i)
    value = len(value)
    return str(value)

# Rebinding a container preserves the original object's aliases.
def container_alias() -> str:
    value = [1, 2]
    alias = value
    value = "done"
    alias.append(3)
    return str(alias) + value

# A chained assignment uses the current binding without inventing inner versions.
def targets() -> int:
    value = "3"
    value = int(value)
    value = other = value + 1
    value, other = other + 1, value
    return value + other

class Holder:
    def __init__(self, text: str) -> None:
        self.text = text

    def length(self) -> int:
        self = self.text
        return len(self)

print(after_rebinding(True), after_rebinding(False))
print(container_alias())
print(targets())
print(Holder("abc").length())

# Empty replacement containers retain the preceding binding's element type.
def inferred_container() -> list[int]:
    value = [1]
    value = []
    print(value)
    return value

# A prior read of None can obtain its optional type from a later assignment.
def inferred_alias() -> list[int | None]:
    value = None
    alias = [value]
    value = 2
    return alias

def inferred_optional() -> int:
    value = None
    print(value)
    value = 3
    return value

print(inferred_container(), inferred_alias(), inferred_optional())

# The RHS retains its old target context even through builtin aliases.
def empty_constructors() -> None:
    value = [1]
    value = empty_list()
    print(value)
    value = builtins.list()
    print(value)

def nothing(n: int) -> None:
    return None

def inferred_none_call() -> list[int | None]:
    value = nothing(1)
    alias = [value]
    value = 4
    return alias

empty_constructors()
print(inferred_none_call())

# A new optional local binding is allowed; explicit return types still apply.
def optional_rebind(value: str | None) -> str | None:
    result = "default"
    result = value
    return result

print(optional_rebind(None), optional_rebind("text"))
