# error: unsupported decorator @property
def property(f):
    return f

class C:
    @property
    def value(self) -> int:
        return 1

print(C().value())
