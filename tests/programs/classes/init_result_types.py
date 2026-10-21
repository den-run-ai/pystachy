# Falsy results still fail, and a returned subclass is named by its actual type.
class BoolResult:
    def __init__(self) -> bool:
        return False


class ListResult:
    def __init__(self) -> list[int]:
        return []


class TupleResult:
    def __init__(self) -> tuple[()]:
        return ()


class Value:
    pass


class SubValue(Value):
    pass


class ObjectResult:
    def __init__(self, choice: int) -> Value:
        if choice < 0:
            return None
        if choice:
            return SubValue()
        return Value()


try:
    BoolResult()
except TypeError as e:
    print("TypeError", e)
try:
    ListResult()
except TypeError as e:
    print("TypeError", e)
try:
    TupleResult()
except TypeError as e:
    print("TypeError", e)
for choose in [-1, 0, 1]:
    try:
        ObjectResult(choose)
        print("object result was None")
    except TypeError as e:
        print("TypeError", e)
