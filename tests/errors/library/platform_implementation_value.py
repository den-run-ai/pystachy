# error: platform_implementation_value.py:5: error: sys.implementation cannot be used as a value (read sys.implementation.name, which is "pystachy")
# Pystachy's sys.implementation has its name only
import sys

impl = sys.implementation
