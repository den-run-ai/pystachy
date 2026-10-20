# error: catching classes that do not inherit from BaseException is not allowed
try:
    print(int("3"))
except (ValueError, int):
    pass
