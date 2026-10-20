# printf-style formatting with a constant format string
name = "Ada"
n = 42
x = 3.14159
neg = -7
print("hello %s" % name, "%d items" % n, "%5d|%-5d|%05d|%+d|% d" % (n, n, n, n, n))
print("%x %X %o %#x %#o %#X" % (255, 255, 8, 255, 8, 255), "%x" % neg)
print("%f %.2f %10.3f %-10.1f| %e %.3E %g %G %.10g" % (x, x, x, x, x, x, x, 1e-10, x))
print("%s %r %a" % ("q'uote", "q'uote", "é"), "%s" % [1, 2], "%r" % {"k": 1}, "%s and %s" % (None, True))
print("%c%c" % (72, "i"), "100%%" % (), "%d%%" % 50, "%5s|%-5s|%.2s" % ("ab", "ab", "abcdef"))
print("%d" % 3.99, "%d" % -3.99, "%i" % True, "%s" % 1.0, "%r" % 0.1, "%.0f" % 2.5, "%.0f" % 3.5)
print("%s" % (1,), "%s-%s" % (1, 2), "%+.2e" % -1234.5, "%08.3f" % -3.14159, "%-8.3f|" % 3.14159)
t = (1, "two")
print("%d=%s" % t)
print("%s %s" % (n,))
