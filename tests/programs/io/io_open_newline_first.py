# CPython's text layer checks newline= before it looks the encoding up
enc = "bo" + "gus"
print("before")
f = open("/dev/null", "w", encoding=enc, newline="zz")
print("not reached")
