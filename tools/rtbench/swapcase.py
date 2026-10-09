import sys
k = len(sys.argv)
s = "hello World, this IS a Test of title-case. " * (25000 * k)
t = 0
for i in range(300):
    t += len(s.swapcase()) + len(s.capitalize())
print(t)
