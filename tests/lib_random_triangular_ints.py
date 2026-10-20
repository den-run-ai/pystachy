# lib/random's triangular() returns its low bound unchanged where the mode's fraction of the
# range divides by zero, and a float otherwise: of int bounds, int | float.
import random

random.seed(1)
print(random.triangular(1, 3), random.triangular(2, 2, 2))
