# error: hasattr() of property 'value' is not supported
class C:
    @property
    def value(self) -> int:
        return 1

c = C()
print(hasattr(c, "value"))
