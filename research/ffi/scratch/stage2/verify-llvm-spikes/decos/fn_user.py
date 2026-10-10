def deco(g):
    return g
@deco
def f(x: int) -> int:
    return x
print(f(1))
