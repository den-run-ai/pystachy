import sys
k = len(sys.argv)
cs = ""
for i in range(32, 127):
    cs += chr(i)
s = "~" * (2000000 * k) + "\n" + "~" * 2000000
n = 0
for i in range(10):
    n += len(s.strip(cs)) + len(s.lstrip(cs + cs + cs))
print(n)
