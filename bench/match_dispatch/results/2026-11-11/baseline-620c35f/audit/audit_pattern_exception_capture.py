class E:
    def __eq__(self, other:int)->bool:
        raise ValueError('bad')
def f()->None:
    n=100
    try:
        match (3,E()):
            case (n,1):pass
    except ValueError:
        print(n)
f()
