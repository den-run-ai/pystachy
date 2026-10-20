# error: cannot import name 'ExitStack' from 'contextlib'
from contextlib import ExitStack

with ExitStack() as stack:
    print(stack)
