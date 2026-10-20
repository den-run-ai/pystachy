# error: static_len_big_int.py:6: error: integer literal does not fit in 64 bits
# a len() test that the types decide still checks its int constant


t = (1, 2)
print("yes" if len(t) < 9223372036854775808 else "no")
