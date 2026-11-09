import math
import sys

NAN = float("nan")
x = float(sys.argv[1]) if len(sys.argv) > 1 else NAN
print(math.isnan(math.fmod(NAN, 1.0)), math.isnan(math.fmod(x, 1.0)), math.fmod(NAN, 1.0) != math.fmod(NAN, 1.0))
