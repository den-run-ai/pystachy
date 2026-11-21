# An or/and of an int and a str is the union where it is an operand too: its operands share no
# scalar type for the operation to run on, so the operation is the union's, the str's here
def scaled(a: int, b: int, flag: bool) -> int | str:
    return ((a if flag else b) or "x") * 2
print(scaled(0, 0, True))
