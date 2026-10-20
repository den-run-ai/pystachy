# error: sys.float_info cannot be used as a value (read its attributes: sys.float_info.max, sys.float_info.epsilon, ...)
# its repr, sys.float_info(max=1.7976931348623157e+308, ...), and its tuple items are not supported
from sys import float_info

print(float_info)
