# A @contextmanager method of a class nested in a class body, which the loader rewrites as it
# rewrites one of a class of the module's body.
from contextlib import contextmanager
from typing import Iterator


class Outer:
    class Res:
        def __init__(self) -> None:
            self.log: list[str] = []

        @contextmanager
        def opened(self, name: str) -> Iterator[str]:
            self.log.append("open " + name)
            yield name.upper()
            self.log.append("close " + name)


r = Outer.Res()
with r.opened("a") as v:
    print(v)
print(r.log)
