# A function read as a value at module level may be called through it before module code has
# assigned a global the function reads: the read raises NameError, as in CPython
def h() -> int:
    return x


fs = [h]
try:
    print(fs[0]())
except NameError as e:
    print("NameError:", e)
x = 1
print(fs[0]())
