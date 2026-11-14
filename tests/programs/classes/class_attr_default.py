# A class-body default reads the class's earlier constant, not the module's global (once rejected).
x = 10


class A:
    x: int = 1
    y: int = x + 1


print(A().y)
