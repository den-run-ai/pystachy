# A UnicodeDecodeError that nothing catches, in a program without try statements (pys_raise)
print("start")
raise UnicodeDecodeError("utf-8", b"a\xc3", 1, 2, "unexpected end of data")
