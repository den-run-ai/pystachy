# error: getattr_hook_field_type.py:13: error: field 'label' of Proxy may be unassigned where it is read, and CPython then calls __getattr__, which returns int, not the field's str: not supported (assign the field on every path of each __init__, before the object is used)
# A field that __init__ may leave unassigned reaches __getattr__ in CPython (#1536): Pystachy
# calls it where its value is one of the field's type, and rejects the read otherwise.
class Proxy:
    def __init__(self, full: bool) -> None:
        if full:
            self.label = "x"

    def __getattr__(self, name: str) -> int:
        return 0


print(Proxy(False).label)
