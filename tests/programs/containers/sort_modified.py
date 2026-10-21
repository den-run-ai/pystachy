# A list that __lt__ grows while it is being sorted: the sort still finishes, then it raises
class D:
    def __init__(self, v: int):
        self.v = v

    def __lt__(self, o: "D") -> bool:
        print("lt", self.v, o.v, len(xs))
        if self.v == 2:
            xs.append(D(9))
        return self.v < o.v


xs = [D(3), D(1), D(2), D(5), D(4), D(0)]
print("sorting")
xs.sort()
print("not reached", [d.v for d in xs])
