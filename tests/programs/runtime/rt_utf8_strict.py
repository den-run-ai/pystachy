# chr() constructs code points, including U+0080..U+00FF. These formerly byte-like
# sequences remain distinct characters in ascii(), repr() and numeric conversion;
# they do not construct malformed UTF-8 now that chr() always encodes its code point.
print(ascii(chr(0xC1) + chr(0xBF)), ascii(chr(0xC0) + chr(0x80)), ascii(chr(0xE0) + chr(0x99) + chr(0xA0)))
print(ascii(chr(0xF0) + chr(0x80) + chr(0x80) + chr(0xA0)), ascii(chr(0xF4) + chr(0x90) + chr(0x80) + chr(0x80)))
print(ascii(chr(0xF7) + chr(0xBF) + chr(0xBF) + chr(0xBF)), ascii(chr(0xF8) + chr(0x90) + chr(0x80) + chr(0x80)))
print(ascii(chr(0xFC) + chr(0x80) + chr(0x80) + chr(0x80)), ascii(chr(0xE9) + "x" + chr(0xC3)), ascii(chr(0xBF) + chr(0xFF)))
print(ascii([chr(0xC1) + chr(0x81), "٠"]), f"{chr(0xE0) + chr(0x82) + chr(0xA0)!a}", ascii(chr(0xF0) + chr(0x90)))
print(len(repr(chr(0xF8) + chr(0x90) + chr(0x80) + chr(0x80))), len(repr(chr(0xFC) + chr(0x80) + chr(0x80) + chr(0x80))))
print(ascii("é€😀" + chr(0x10FFFF) + chr(0xD800)), ascii("\x7f\x85\xa0"))
# U+0085 and U+00A0 are Unicode spaces; Unicode decimal digits still parse as digits.
print(int(chr(0xA0) + "7" + chr(0x85)), int(chr(0x85) + "-1f" + chr(0xA0), 16), float(chr(0xA0) + "7.5" + chr(0x85)))
print(int("٠٧"), float("١.٥" + chr(0xA0)), int(chr(0x85) + "　" + "12"))
