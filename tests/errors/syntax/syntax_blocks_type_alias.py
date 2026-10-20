# error: syntax_blocks_type_alias.py:7: error: too many statically nested blocks
# a type alias's value is compiled where the type statement is, as a function of its own: 22
# comprehensions nested in it are too many, although nothing evaluates it
print("never")
n = 0
for i in range(3):
    type Deep = [[[[[[[[[[[[[[[[[[[[[[0 for x0 in n] for x1 in n] for x2 in n] for x3 in n] for x4 in n] for x5 in n] for x6 in n] for x7 in n] for x8 in n] for x9 in n] for x10 in n] for x11 in n] for x12 in n] for x13 in n] for x14 in n] for x15 in n] for x16 in n] for x17 in n] for x18 in n] for x19 in n] for x20 in n] for x21 in n]
    n += i
