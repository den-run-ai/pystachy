# error: module 'importlib.util' has no attribute 'find_spec'
import importlib.util

print(importlib.util.find_spec("colorsys") is None)
