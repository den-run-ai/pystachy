"""Choose squared error (0) or absolute error (1) from the command line."""
from collections.abc import Callable
import sys

from scoring import absolute_error, score, squared_error

losses: list[Callable[[float, float], float]] = [squared_error, absolute_error]
loss = losses[int(sys.argv[1]) if len(sys.argv) > 1 else 0]
print(score(loss, [1.0, 2.0, 4.0], [1.0, 3.0, 2.0]))
