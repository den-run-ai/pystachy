# Number literals CPython's tokenizer accepts: leading zeros before a fraction, an exponent or
# a "j", single underscores between digits (and after a base prefix), any case of the prefix
def never(x):
    return 09j, 0_7j, 1_000_000j, 00j, 1..real, 1.5J


print(09.5, 0_7.5, 0_7e1, 00, 0_0, 00_0, 0e0, 1_0.0_1, 1E5, .5e-1_0)
print(0O17, 0B11, 0X1F, 0x_f, 0b_1, 0o_7_7, 0xdead_beef)
