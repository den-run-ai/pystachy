# Builtins consume their arguments using normal expected types. A forwarding
# return marker must not reach sorted()'s comparison or nested iterable arguments.
def empty(n):
    return []


def mapping(n):
    return {}


def ordered(n):
    return sorted(empty(n))


def copied(n):
    return list(empty(n))


def copied_mapping(n):
    return dict(mapping(n))


def immutable(n):
    return tuple(empty(n))


def unique(n):
    return set(empty(n))


def total(n):
    return sum(empty(n))


def minimum(n):
    try:
        return min(empty(n))
    except ValueError:
        return n


def maximum(n):
    try:
        return max(empty(n))
    except ValueError:
        return n


def method(n):
    return empty(n).copy()


sort_alias = sorted


def aliased(n):
    return sort_alias(empty(n))


print(ordered(1), copied(1), copied_mapping(1), immutable(1), len(unique(1)))
print(total(1), minimum(2), maximum(3), method(1), aliased(1))
