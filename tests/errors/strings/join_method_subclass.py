# error: join_method_subclass.py:17: error: expected list[float | int], got list[float]
# A method's fresh list where a joined list is kept, called on an object whose class another
# class derives from: the call may run either class's method, so no join gives the method a
# return type (annotate it).
class Ops:
    def scale(self, u, k):
        return [x * k for x in u]


class Fast(Ops):
    pass


def run(ops: Ops, n: int):
    u = [1] * n
    for _ in range(2):
        u = ops.scale(u, 0.5)
    return u


print(run(Fast(), 2))
