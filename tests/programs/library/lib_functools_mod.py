# lru_cache() and cache() in an imported module (mods/cachemod.py), called from the program, and the
# program's own def decorated with functools.lru_cache as an attribute of the module
import functools

import mods.cachemod as cm
from mods.cachemod import CALLS, depth, label

print(label(1, "file"), label(2, "file"), label(1, "file"), label(3, "dir"), label(2, "file"))
print(label.cache_info(), cm.label.cache_info())
print(depth(5), depth(7), depth.cache_info())
print(CALLS)


@functools.lru_cache(maxsize=4)
def area(w: int, h: int) -> int:
    CALLS.append(f"area {w} {h}")
    return w * h


print(area(2, 3), area(2, 3), area(3, 2), area.cache_info(), CALLS[-2:])
cm.depth.cache_clear()
print(depth.cache_info(), depth(1), depth.cache_info())
