# error: deriving from UnicodeEncodeError is not supported
class U(UnicodeEncodeError):
    pass


e = U("ascii", "x", 0, 1, "ordinal not in range(128)")
print(str(e))
