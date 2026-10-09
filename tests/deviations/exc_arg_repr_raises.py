# Documented deviation: an exception computes str() and repr() of its arguments as it is made, so
# an argument whose __repr__ raises makes raise KeyError(P()) raise that ValueError instead.
# CPython prints "caught KeyError" (KeyError's str() calls the repr only when it is asked for).
class P:
    def __repr__(self) -> str:
        raise ValueError("repr failed")


try:
    raise KeyError(P())
except KeyError:
    print("caught KeyError")
except ValueError as e:
    print("caught ValueError", e)
