# error: 'type[object]' has no method 'make'
class A:
    @classmethod
    def make(cls) -> "A":
        return cls()


class C:
    pass


ks: list[type] = [A, C]
print(ks[0].make())
