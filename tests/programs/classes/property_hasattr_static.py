# hasattr() of a property in a template's test (#486): decided at run time by its getter
class C:
    @property
    def value(self) -> int:
        return 1

def read(c):
    if hasattr(c, "value"):
        print("present")
read(C())
