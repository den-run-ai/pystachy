# pytest's _bestrelpath_cache: dict[K, V] with __slots__ and __missing__, which computes, stores
# and returns the value for a key it has not seen (a str path for pytest's Path).

import os


def bestrelpath(directory: str, dest: str) -> str:
    # (pytest's, by os.path.relpath alone)
    if dest == directory:
        return os.curdir
    return os.path.relpath(dest, directory)


class _bestrelpath_cache(dict[str, str]):
    __slots__ = ("path",)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def __missing__(self, path: str) -> str:
        r = bestrelpath(self.path, path)
        self[path] = r
        return r


cache = _bestrelpath_cache("/a/b")
print(cache["/a/b/c/d.py"], cache["/a/x.py"], cache["/a/b"], len(cache), sorted(cache.items()), cache.path)
print(cache["/a/x.py"], len(cache), hasattr(cache, "__dict__"))
