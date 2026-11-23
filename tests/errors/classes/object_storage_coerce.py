# error: expected int, got object (narrow a value of object with isinstance() first, as `if isinstance(x, int):` narrows x to an int; a test does not narrow a module's variable: test it in a function)
# a value of object where an int is expected, without a test of its type
x: object = 1
n: int = x
print(n)
