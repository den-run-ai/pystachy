# error: expected type[object], got <built-in function int>
class A:
    pass


k: type = A
k = int
print(k)
