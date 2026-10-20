# hasattr() of a property (#486): its getter runs, and AttributeError means False
class C:
    @property
    def value(self) -> int:
        return 1

c = C()
print(hasattr(c, "value"))
