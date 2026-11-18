# A class template (an __init__ parameter without an annotation) whose fields are annotated
# float and given ints (#1534): a class-body field, whose join its specializations share, and a
# field annotated in __init__, which each specialization types.
class Acc:
    scale: float = 1

    def __init__(self, start):
        self.start = start
        self.total: float = 0

    def add(self, v: float) -> None:
        self.total += v * self.scale


a = Acc(1)
b = Acc("x")
a.add(2.5)
b.scale = 0.5
b.total = 3
b.add(1.5)
print(a.start, a.scale, a.total, b.start, b.scale, b.total, Acc.scale)
print(isinstance(a.scale, int), isinstance(b.scale, int), isinstance(a.total, int), isinstance(Acc(2).total, int))
