# error: module 'sqlite3' is not supported: it is not a builtin module and there is no sqlite3.py on the module path
try:
    import sqlite3
except ImportError:
    print("sqlite3 is required")
    raise SystemExit(1)
