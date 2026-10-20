# error: the attributes of an exception (e.args) are not supported; str(e) and repr(e) are
try:
    print(int("x"))
except ValueError as e:
    print(e.args)
