# error: math.dist() of a tuple[int,float] needs items of a single type
import math

print(math.dist((1, 2.5), (0.0, 0.0)))
