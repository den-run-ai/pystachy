# pystachy: dynamic-any
# Imported unsupported declarations still define comparison methods. An active
# call must report the limitation, without falling through to reflected code.
from typing import Any
from devmods.cmp_declined import Annotated, Returned, Reflected


annotation: Any = Annotated()
returned: Any = Returned()
peer: Any = Reflected()
for value in [annotation, returned]:
    for op in range(4):
        try:
            if op == 0:
                print(value == peer)
            elif op == 1:
                print(value != peer)
            elif op == 2:
                print(value == value)
            else:
                print(value != value)
        except TypeError as error:
            print(op, str(error))
        finally:
            print("cleanup", op)
# An available left method wins before an unavailable reflected method.
print(peer == annotation, peer == returned)
# Identity-first searches and unused comparisons still compile and execute.
print(annotation in [annotation], returned in [returned])
