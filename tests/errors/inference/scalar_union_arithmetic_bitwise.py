# error: closed numeric union arithmetic supports +, -, *, /, //, % and unary + or -; narrow other operations first
def bitwise(value: int | float) -> int | float:
    return value & 2
bitwise(3)
