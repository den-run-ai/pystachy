# error: with suppress(...) as x: is not supported (x would be None, what its __enter__ returns)
from contextlib import suppress

with suppress(KeyError) as nothing:
    print(nothing)
