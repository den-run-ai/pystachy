# error: unsupported operand type(s) for *: 'int' and 'NoneType'
def fact(n: int):
    if n > 0:
        fact(n - 1)
    return 1 * None

print(fact(5))
