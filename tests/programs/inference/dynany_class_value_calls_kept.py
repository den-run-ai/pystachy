# pystachy: dynamic-any
# A module that opts in to dynamic Any and names type[C] keeps the class values of a display of
# unrelated classes: a call through one runs its class's constructor.
class A:
    pass


class C:
    pass


def name(k: type[A]) -> str:
    return k.__name__


for k in [A, C]:
    print(type(k()).__name__)
print(name(A))
