try:
    from . import broken
except ImportError:
    print("relative fallback")
try:
    from loader.fl import _cext
except ImportError:
    print("no _cext")
