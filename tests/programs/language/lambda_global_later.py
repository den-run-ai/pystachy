# A module-level lambda called before module code has assigned a global it reads: the read
# raises NameError, as in CPython, whether the lambda is called through a variable, a list or
# a builtin's key=
f = lambda: x
try:
    print(f())
except NameError as e:
    print("NameError:", e)
fs = [lambda: y]
try:
    print(fs[0]())
except NameError as e:
    print("NameError:", e)
try:
    print(sorted([2, 1], key=lambda v: v * z))
except NameError as e:
    print("NameError:", e)
x = "hello"
y = 2
z = -1
print(f(), fs[0](), sorted([2, 1], key=lambda v: v * z))
