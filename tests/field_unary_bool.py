# A field takes the type of the value __init__ assigns it, which for -, + and ~ of a bool is
# int, as in any expression: self.neg = -True holds -1 and later any int.
class Flags:
    def __init__(self, on: bool) -> None:
        self.neg = -True
        self.pos = +on
        self.twice = -(-on)
        self.inv = ~(1 if on else 2)
        self.half = -(0.5 if on else 1.5)


f = Flags(True)
print(f.neg, f.pos, f.twice, f.inv, f.half)
f.neg -= 2
f.pos = 7
print(f.neg, f.pos, Flags(False).pos, Flags(False).half)
