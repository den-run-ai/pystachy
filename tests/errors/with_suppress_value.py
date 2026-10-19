# error: contextlib.suppress() is supported with exception classes, as a with statement's item
from contextlib import suppress

with suppress("KeyError"):
    print({}["k"])
