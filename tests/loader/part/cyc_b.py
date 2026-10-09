try:
    from loader.part.cyc_a import f
except ImportError:
    def f() -> str:
        return "slow"
try:
    from loader.part.cyc_a import v
    w = "fast"
except ImportError:
    w = "slow"


def g() -> str:
    return f()
