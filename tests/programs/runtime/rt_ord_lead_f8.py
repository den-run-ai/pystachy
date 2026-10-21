# ord() of four bytes that 0xF8 leads: no UTF-8 sequence starts above 0xF4, so CPython sees the four
# characters chr() made
s = chr(0xF8) + chr(0x90) + chr(0x80) + chr(0x80)
print(len(s), ascii(s))
print(ord(s))
