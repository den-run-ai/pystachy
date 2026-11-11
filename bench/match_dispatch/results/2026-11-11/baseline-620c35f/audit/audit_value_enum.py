from enum import Enum
class C(Enum):
    A=1
    B=2

def f(x:C)->str:
    match x:
        case C.A: return 'a'
        case C.B: return 'b'
    return 'none'
print(f(C.A),f(C.B))
