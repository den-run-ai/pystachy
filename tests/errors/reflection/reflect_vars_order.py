# error: reflect_vars_order.py:14: error: vars() of Point is not supported: the order its __init__ assigns attributes in is not known at compile time
# Two attributes first assigned in one branch: their order in the __dict__ depends on the run
class Point:
    def __init__(self, x: int) -> None:
        self.x = x
        if x > 0:
            self.a = 1
            self.b = 2
        else:
            self.b = 3
            self.a = 4


print(vars(Point(1)))
