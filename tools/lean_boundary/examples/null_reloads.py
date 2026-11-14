# Null-check removals justified through memory: a field reloaded from the same
# object, a field reloaded across a write of another field, a module global
# reloaded across a list write, a closure cell reloaded in a lambda, and a
# parameter reloaded from the cell its nested function shares. The access model
# proves them (GUARDS.md).
class Inner:
    def __init__(self, v: int) -> None:
        self.v = v
        self.w = v + 1


class Holder:
    def __init__(self, inner: Inner | None) -> None:
        self.inner = inner
        self.count = 0


log: list[str] = []
current: Inner | None = Inner(5)


def field_reload(h: Holder) -> int:
    if h.inner is None:
        return 0
    return h.inner.v + h.inner.w


def field_reload_other_field(h: Holder) -> int:
    if h.inner is None:
        return 0
    h.count = h.count + 1
    return h.inner.v + h.count


def global_reload() -> int:
    if current is None:
        return 0
    t = current.v
    log.append("between")
    return t + current.v


def through_own_cell(h: Holder) -> int:
    def peek() -> int:
        return h.count

    if h.inner is None:
        return peek()
    return h.inner.v + h.inner.w + peek()


def captured(inner: Inner):
    f = inner.v
    return lambda: f + inner.w + inner.w


h = Holder(Inner(2))
print(field_reload(h), field_reload(Holder(None)), field_reload_other_field(h), global_reload(), len(log))
print(captured(Inner(4))(), through_own_cell(h), through_own_cell(Holder(None)))
