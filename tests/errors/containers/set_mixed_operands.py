# error: set_mixed_operands.py:4: error: unsupported operand types for |: set[int] and set[str] (a set holds elements of one type)
s = {1}
t = {"a"}
print(s | t)
