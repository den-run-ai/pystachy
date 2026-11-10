# error: closed numeric union arithmetic supports +, -, *, /, //, % and unary + or -; narrow other operations first
# A power of ints is a float for a negative exponent, so a conditional operand keeps its int
# only for a literal exponent that is not negative: any other power stays the union's
def power(a: int, b: int, n: int, flag: bool) -> int | float:
    return (a if flag else b) ** n
print(power(2, 3, -1, True))
