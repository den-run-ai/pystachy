# CPython's traceback prints a SyntaxError without a message as "<no detail available>"
print("before")
raise SyntaxError
