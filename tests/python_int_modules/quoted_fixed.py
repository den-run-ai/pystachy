# A module that does not opt in, with quoted annotations: its ints are checked 64-bit values.
def halve(x: "int") -> "int":
    return x // 2
