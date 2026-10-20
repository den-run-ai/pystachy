# error: unsupported call math.gcd(float,int)
# (CPython raises TypeError: 'float' object cannot be interpreted as an integer); the message
# names the arguments' own types (#324)
import math

print(math.gcd(1.5, 2))
