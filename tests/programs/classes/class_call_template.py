# C.m(o, ...) through a class template (an __init__ parameter without an annotation) calls the
# method of o's specialization, C's for its types, as CPython calls C's function
class C:
    def __init__(self, n):
        self.n = n

    def size(self, extra: int = 0) -> int:
        return len(str(self.n)) + extra


print(C.size(C(12345)), C.size(C("ab")), C.size(C(1.5), 10))
