# error: hasattr() of property 'value' is not supported
class C:
    @property
    def value(self) -> int:
        return 1

def read(c):
    if hasattr(c, "value"):
        print("present")
read(C())
