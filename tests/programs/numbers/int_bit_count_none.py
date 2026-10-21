# bit_count() of a bool | None that is None: CPython's AttributeError
import sys

b: bool | None = None if len(sys.argv) > 1 else True
print(b.bit_count())
