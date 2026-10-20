from typing import Optional


class Box:
    def __init__(self, inner: Optional["Box"]):
        self.inner = inner
        self.n = 1

    def __str__(self) -> str:
        return str(self.inner.n)


print("total:", Box(None))
