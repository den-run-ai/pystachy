# error: class_nested_generic.py:8: error: class Box.Meta is not supported: a class nests classes in the body of a class statement of a module's body (not of an if or try statement), but not of an enum class or a generic class of PEP 695
# A class nested in the body of a generic class of PEP 695, whose type parameters it may read,
# stays unsupported.
class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item

    class Meta:
        name = "box"


print(Box(1).item, Box.Meta.name)
