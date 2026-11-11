# type(x) used as a dict key / compared (97 uses), e.g. `type(left) is type(right)`, `{type(t): handler}`
class A:
    pass
class B(A):
    pass
def same(x: A, y: A) -> bool:
    return type(x) is type(y)
print(same(A(), A()), same(A(), B()), type(B()).__name__)
