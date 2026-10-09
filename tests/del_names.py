# del of a variable unbinds it: later reads raise UnboundLocalError (locals) or NameError (globals)
x = 1
y = [1, 2]
for i in range(3):
    t = i * 2
del t, i
print(x)
def f(a: int) -> int:
    b = a + 1
    del b
    c = 5
    del c
    c = 6
    return c
print(f(1))
def g() -> int:
    return x
print(g())
del x
def h() -> int:
    z = 1
    del z
    return z
print(h())
