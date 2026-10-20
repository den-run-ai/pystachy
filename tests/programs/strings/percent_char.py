# %c takes a one-character str (also a non-ASCII one) or a code point, pads it to the width
# (left with '-'; '0', '+', ' ', '#' and a precision change nothing), and rejects a longer str
a = "a"
e = "\xe9"
euro = "€"
n = 66
print("[%c] [%3c] [%-3c] [%c] [%3c] [%-4c]" % (a, a, a, e, e, euro))
print("[%05c] [%05c] [%-05c] [%+3c] [%#3c] [% 3c] [%.2c] [%3.1c]" % (a, n, a, a, a, n, a, a))
print("[%c|%3c|%-2c|%2c]" % (a, n, True, 0x20AC), "%c%c" % (72, "i"))
words = ["x", "yz", ""]
for w in words:
    print("[%2c]" % w)
