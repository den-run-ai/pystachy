# error: cannot tell whether module 'eload.unsure' has bound 'x' when this optional import runs
try:
    from eload.unsure import x
except ImportError:
    print("fallback")
