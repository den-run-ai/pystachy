# error: from eload.unsure import x in an optional import (try: ... except ImportError:) is not supported where the code of module 'eload.unsure' may leave 'x' unbound
try:
    from eload.unsure import x
except ImportError:
    print("fallback")
