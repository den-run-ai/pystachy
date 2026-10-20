# error: import_setattr_base.py:6: error: class emods.attrhooks.FrozenRetry is not supported: the special method __setattr__ of its base emods.attrhooks.FrozenError is not supported (CPython calls it to assign each attribute)
# (CPython's FrozenRetry("again") raises AttributeError where its __init__ assigns self.tries)
import emods.attrhooks

try:
    raise emods.attrhooks.FrozenRetry("again")
except AttributeError as e:
    print(e)
