# pystachy: python-int
def f(x:int)->str:
    match x:
        case (a,b): return 'tuple'
        case _: return 'scalar'
print(f(1),f(1 << 100),f(-(1 << 100)))
