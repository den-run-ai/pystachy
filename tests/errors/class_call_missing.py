# error: type object 'C' has no attribute 'make'
class C:
    @staticmethod
    def build() -> int:
        return 1


print(C.make())
