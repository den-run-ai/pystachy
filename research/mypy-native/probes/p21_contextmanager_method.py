# @contextmanager generator methods used in with (42 uses), e.g. binder.frame_context / scope.push
from contextlib import contextmanager
from collections.abc import Iterator
class Scope:
    def __init__(self) -> None:
        self.stack: list[str] = []
    @contextmanager
    def push(self, name: str) -> Iterator[None]:
        self.stack.append(name)
        try:
            yield
        finally:
            self.stack.pop()
s = Scope()
with s.push("a"):
    with s.push("b"):
        print(s.stack)
print(s.stack)
