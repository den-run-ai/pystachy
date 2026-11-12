from typing import final
@final
class A:
    pass
class B:
    @final
    def m(self) -> int:
        return 1
print(A.__final__, B.m.__final__)
