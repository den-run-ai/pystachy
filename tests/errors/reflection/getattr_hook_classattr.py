# error: getattr_hook_classattr.py:9: error: the special method __getattr__ is not supported (CPython calls it for each attribute it does not find) as a class attribute (define it with def)
# CPython calls what a class attribute binds __getattr__ to as it calls a def; Pystachy calls the
# def only (#1536).
def hook(o: "Proxy", name: str) -> int:
    return 0


class Proxy:
    __getattr__ = hook


print(Proxy().depth)
