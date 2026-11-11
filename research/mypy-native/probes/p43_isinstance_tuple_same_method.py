# isinstance tuple where only a base-declared method is used afterwards (no narrowing needed)
class Type:
    def n(self) -> str:
        return "t"
class A(Type):
    pass
class B(Type):
    pass
class C(Type):
    pass
def f(t: Type) -> bool:
    return isinstance(t, (A, B))
print(f(A()), f(B()), f(C()))
