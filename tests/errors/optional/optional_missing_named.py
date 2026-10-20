# error: there is no missing_mod_xyz.py on the module path; an optional import whose except clause names the exception (as e) needs its module
try:
    import missing_mod_xyz
except ImportError as e:
    print("missing:", e)
