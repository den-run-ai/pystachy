# The statements after an optional import's imports keep its except clause where they may raise
# a subclass of ImportError in any way (#1504): a raise of their own, a method, a property, an
# operator method or an iterator.
class Missing(ImportError):
    pass


class Backend:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    def load(self) -> str:
        if not self.ok:
            raise Missing("load")
        return "loaded"

    @property
    def name(self) -> str:
        if not self.ok:
            raise Missing("name")
        return "named"

    def __add__(self, other: int) -> int:
        if not self.ok:
            raise Missing("add")
        return other + 1

    def __iter__(self) -> "Backend":
        return self

    def __next__(self) -> int:
        raise Missing("next")


flag = len("x") == 1
try:
    import json

    if flag:
        raise Missing("direct")
    a = "unreached"
except ImportError as e:
    a = f"handler: {e}"
print(a)

bad = Backend(False)
good = Backend(True)
try:
    import json

    b = good.load() + " " + bad.load()
except ImportError as e:
    b = f"handler: {e}"
print(b)

try:
    import json

    c = good.name + " " + bad.name
except ImportError as e:
    c = f"handler: {e}"
print(c)

try:
    import json

    d = str(good + 1) + str(bad + 1)
except ImportError as e:
    d = f"handler: {e}"
print(d)

try:
    import json

    total = 0
    for x in bad:
        total += x
    e1 = str(total)
except ImportError as e:
    e1 = f"handler: {e}"
print(e1)
