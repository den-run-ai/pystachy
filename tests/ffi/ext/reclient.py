import sys
import reent
blocks = sys.getallocatedblocks()
r = reent.outer(300)
print(r, r == sum(3 * (20 * i + 190) + 1 for i in range(300)))
print("CPython blocks bounded:", sys.getallocatedblocks() - blocks < 3000)
