# a NUL inside a spec: runtime.c's message stopped at it
spec = "<\x005"
x = 5
print(f"{x:{'<5'}}|")
print(f"{x:{spec}}")
