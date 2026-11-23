# vars() of an object whose fields have every storage width: a reference (str, a union, an Optional
# int or float, a tuple) is a pointer, of 4 bytes on wasm32, beside 8-byte ints and floats and a
# 1-byte bool. Each field reads as itself, not as part of its neighbour (wasm/README.md).
from typing import Optional


class Mixed:
    def __init__(self, k: int) -> None:
        self.u: int | str = k if k > 1 else "s"
        self.oi: Optional[int] = None if k == 0 else k
        self.of: Optional[float] = 1.5 if k else None
        self.t: tuple[int, str] = (k, "t")
        self.f = 2.5
        self.b = k > 1
        self.s: str | None = None
        self.n = 7


for k in range(4):
    print(vars(Mixed(k)))
