# error: expected bool | None, got int
# (CPython raises ValueError: stack_effect: jump must be False, True or None)
from _opcode import stack_effect

stack_effect(1, jump=1)
