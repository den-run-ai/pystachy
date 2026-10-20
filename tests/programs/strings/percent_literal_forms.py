# % formatting compiles where the format string is a literal, in each of its forms; one computed
# at run time is rejected (tests/errors/strings/percent_runtime_*.py)
fmt = "%d"
n = 3
print("%d" " items" % n, ("[%s]") % fmt, r"%s\t" % "x", """%-4s|""" % "ab", "%s" % fmt)
print(("%d" "/%d") % (n,))
