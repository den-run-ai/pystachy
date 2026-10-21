# A specialized constructor must check the initializer's annotated return too.
class GenericResult:
    def __init__(self, value) -> int:
        self.value = value
        print("generic init", value)
        return 0


try:
    GenericResult(1)
except TypeError as e:
    print("TypeError", e)
try:
    GenericResult("text")
except TypeError as e:
    print("TypeError", e)
