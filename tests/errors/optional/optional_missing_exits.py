# error: optional_missing_exits.py:5: error: module 'sqlite3' is not supported: it is not a builtin module and there is no sqlite3.py on the module path
# A handler that ends the program another way than by a raise makes the module required too.
import sys

try:
    import sqlite3
except ImportError:
    print("this program needs sqlite3")
    sys.exit(1)
print("have sqlite3")
