# C.m(o, ...) through a class outside any hierarchy calls its method on o, as o.m(...) does, also
# with defaults and keyword arguments (C.__init__(o, ...) is still rejected: class_call_init.py)
class C:
    def __init__(self) -> None:
        self.n = 1

    def size(self) -> int:
        return self.n

    def add(self, k: int = 1, *, scale: int = 1) -> int:
        self.n += k * scale
        return self.n


c = C()
print(C.size(C()))
print(C.add(c), C.add(c, 2), C.add(c, k=3, scale=2), C.size(c))
