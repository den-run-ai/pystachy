# error: type object 'A' has no attribute '__final__'
# (@final is applied as the identity: CPython's sets __final__, which Pystachy does not)
from typing import final


@final
class A:
    pass


print(A.__final__)
