# int() of a digit's overlong UTF-8 form (U+0667 in three bytes): CPython sees three characters, the
# first no digit; its message shows the repr's first 200 characters, here all zeros
print(int("0" * 250 + "٧"))
print(int("0" * 250 + chr(0xE0) + chr(0x99) + chr(0xA7)))
