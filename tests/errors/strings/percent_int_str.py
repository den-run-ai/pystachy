# error: percent_int_str.py:4: error: unsupported operand type(s) for %: 'int' and 'str'
# the left operand is not a str: CPython's TypeError, at compile time
n = 3
print(n % "a")
