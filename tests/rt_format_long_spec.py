# runtime.c cut this message at 511 bytes; runtime.py reports the whole spec, as CPython does
spec = "<" + "5" * 3 + "a" * 600 + "x"
x = 5
print(f"{x:{'>8'}}|")
print(f"{x:{spec}}")
