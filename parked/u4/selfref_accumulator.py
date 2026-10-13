class R:
    def __init__(self, ok: bool, v):
        self.ok = ok
        self.v = v

    def agg(self, other):
        if not other:
            return self
        return R(self.ok and other.ok, self.v)


def run(xs):
    result = None
    for x in xs:
        result = R(x > 0, x).agg(result)
    return result


r = run([1, 2])
print(r.ok if r is not None else None, r.v if r is not None else None)
