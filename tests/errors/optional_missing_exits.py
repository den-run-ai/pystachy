# error: optional_missing_exits.py:5: error: module 'json' is not supported: it is not a builtin module and there is no json.py on the module path
# A handler that ends the program another way than by a raise makes the module required too.
import sys

try:
    import json
except ImportError:
    print("this program needs json")
    sys.exit(1)
print("have json")
