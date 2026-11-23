import gc
import threading
from _weakref import ref


def make_refs(count: int):
    return [ref(threading.Thread()) for _ in range(count)]


live = threading.Thread(name="kept")
for _ in range(2):
    refs = make_refs(32)
    gc.collect()
    # A conservative stack scan can keep individual targets alive.
    print(any(r() is None for r in refs), len(threading._dangling) < len(refs))
    print(live in threading._dangling, any(t is live for t in threading._dangling))
print(live.name)
