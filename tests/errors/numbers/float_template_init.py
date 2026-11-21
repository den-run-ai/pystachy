# error: expected float, got int (write a float literal like 1.0, or use float())
# A hand-written constructor compiles for an int given to its float parameter (#1534), but
# not a class template's, whose arguments type its specialization
class Acc:
    def __init__(self, start, scale: float) -> None:
        self.start = start
        self.scale = scale


print(Acc(1, 2).scale)
