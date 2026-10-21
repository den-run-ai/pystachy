# error: method 'C.m' cannot be used as a value (call it)
class C:
    def m(self) -> int:
        return 1


f = C.m
