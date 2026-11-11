from dataclasses import dataclass
@dataclass
class P:
    x:int
@dataclass
class C:
    p:P|None

def f(x:C)->int:
    match x:
        case C(P(n)):return n
    return 0
print(f(C(None)),f(C(P(3))))
