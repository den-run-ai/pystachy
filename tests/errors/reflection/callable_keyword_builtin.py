# error: keyword calls through Callable require native defs, closures or nonvirtual methods; builtin targets are not supported
from typing import Callable

fn: Callable[[int], int] = abs
print(fn(x=2))
