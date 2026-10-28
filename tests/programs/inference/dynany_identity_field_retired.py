# pystachy: dynamic-any
# A pre-initialization barrier retires the sharing candidate. Later write-backs
# must keep using ordinary object snapshots across a call that replaces the field.
from typing import Any
class P:
    def __init__(self, n: int) -> None:
        self.pos = n

def renew(p: P) -> None:
    p.pos = 3000

def target(p: P) -> None:
    try:
        x = 0
    except ValueError:
        x = 1
    x = p.pos
    p.pos = x
    renew(p)
    p.pos = x
    a: Any = p.pos
    b: Any = x
    print(p.pos, a, b, a is b)

target(P(int("1000")))
