# error: 'type[object]' has no method 'build'
# No class of the program has such a class method or static method.
class A:
    @classmethod
    def make(cls) -> "A":
        return cls()


class C:
    pass


ks: list[type] = [A, C]
print(ks[0].build())
