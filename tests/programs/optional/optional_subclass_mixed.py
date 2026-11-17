# Sites that keep today's form do not keep a program's other optional imports from keeping their
# except clauses (#1504): one whose handler rebinds the imported module, and lib's statistics,
# whose statement after its import makes a namedtuple class.
import statistics


class Missing(ImportError):
    pass


def need(flag: bool) -> int:
    if flag:
        raise Missing("unavailable")
    return 1


try:
    import json

    a = need(False)
except ImportError:
    json = None
    a = 0

try:
    import json

    b = need(True)
except ImportError:
    b = -1
print(a, b, json.dumps([a, b]), statistics.median([3, 1, 2]))
