# error: unsupported operand type(s) for *: 'int' and 'NoneType'
def procedure(n: int) -> None:
    if n > 0:
        return n * procedure(n - 1)

procedure(5)
