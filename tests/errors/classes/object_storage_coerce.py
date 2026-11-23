# error: expected int, got object (narrow a value of object with isinstance() first, as `if isinstance(x, int):` narrows x to an int)
# a value of object where an int is expected, without a test of its type
x: object = 1
n: int = x
print(n)
