# b[i] = x checks the byte before the index, as CPython does.
b = bytearray(2)
for i, x in ((5, 300), (5, 7), (0, -1), (1, 255)):
    try:
        b[i] = x
        print(b)
    except (ValueError, IndexError) as e:
        print(type(e).__name__, e)
