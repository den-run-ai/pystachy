# error: unsupported call math.prod(list[int],tuple[int,int])
# (CPython repeats the tuple: (1, 2, 1, 2); a tuple's length is part of its type here)
import math

print(math.prod([2], start=(1, 2)))
