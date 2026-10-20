def trace(f):
    print("tracing", f.__name__)
    return f


class Counter:
    @trace
    def step(self, by: int) -> int:
        return by
