# error: unsupported operand types for |: dict[str,int] and dict[str,float] (a dict holds keys and values of one type each)
# (CPython's result holds both value types: {'x': 1, 'y': 2.5})
a = {"x": 1}
b = {"y": 2.5}
print(a | b)
