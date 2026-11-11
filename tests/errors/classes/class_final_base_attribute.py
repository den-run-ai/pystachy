# error: @final on class A is not supported where the body of Base binds __final__
# (CPython's @final sets A's __final__ to True; without it A would read Base's)
from typing import final


class Base:
    __final__ = False


@final
class A(Base):
    pass


print(A.__final__, A().__final__)
