# error: reflected_subclass.py:15: error: reflected operator methods are not supported (Plain | Sub calls Sub.__ror__)
# Sub derives from Plain and has a __ror__ that Plain has not, so CPython calls Sub.__ror__(sub,
# plain) before Plain.__or__ (inheritance is allowed for exception classes)
class Plain(Exception):
    def __or__(self, o: "Plain") -> str:
        return "Plain.__or__"


class Sub(Plain):
    def __ror__(self, o: Plain) -> str:
        return "Sub.__ror__"


print(Sub() | Plain())  # (Sub.__or__ is Plain's, called first)
print(Plain() | Sub())
