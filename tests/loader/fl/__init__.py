print("fl init")
try:
    from . import _speedups
except ImportError:
    print("no _speedups")
X = 1
