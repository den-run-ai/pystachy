REGISTRY: list[str] = []


def register(name: str):
    def wrap(f):
        REGISTRY.append(name)
        return f
    return wrap


@register("add")
def add(a, b):
    return a + b
