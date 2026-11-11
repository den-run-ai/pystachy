from dataclasses import dataclass
@dataclass
class P:
    x:int

def f(x:P|None)->int:
    match x:
        case P():return 1
    return 0
print(f(None),f(P(3)))
