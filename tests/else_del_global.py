# A global deleted in a while loop's else block is unbound after the loop
import sys

y = 2
n = len(sys.argv)
for a in sys.argv:
    if a == "x":
        break
else:
    n += 1
print(n, y)
while n > 5:
    n -= 1
else:
    del y
print("after")
print(y)
