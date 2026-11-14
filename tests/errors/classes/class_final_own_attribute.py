# error: @final on class A is not supported where its body binds __final__
# (CPython's @final sets __final__ to True over the body's value, which the class would read where
# the loader drops the decorator)
from typing import final


@final
class A:
    __final__ = False


print(A.__final__)
