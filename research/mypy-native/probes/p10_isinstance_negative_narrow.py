# `if not isinstance(x, A): return` then use; and else-branch narrowing to the remaining member of a union
class A:
    def a(self) -> str:
        return "a"
class B:
    def b(self) -> str:
        return "b"
def f(x: A | B) -> str:
    if isinstance(x, A):
        return x.a()
    else:
        return x.b()
print(f(A()), f(B()))
