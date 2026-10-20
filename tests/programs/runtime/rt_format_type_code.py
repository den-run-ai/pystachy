# the presentation type is a code point: NUL is a float's default type, and CPython writes other
# unknown types as escapes
nul = "\x00"
f = 2.5
print(f"{f:{nul}}", f"{f:{'8' + nul}}|")
x = 7
print(f"{x:{'é'}}")
