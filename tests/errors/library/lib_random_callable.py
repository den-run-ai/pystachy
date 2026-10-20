# error: converting inherited method Random.uniform to Callable requires compatible signatures and annotated return types throughout its hierarchy
# lib/random's module functions are a Random's bound methods, which upstream does not annotate: of
# them, only random() and getrandbits(), lib/_pyrandom's, convert to a typed Callable (lib/README.md)
import random
from typing import Callable

random.seed(3)
draw: Callable[[float, float], float] = random.uniform
print(draw(1.0, 2.0))
