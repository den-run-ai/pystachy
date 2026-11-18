# urllib.parse._Quoter as CPython 3.13 writes it (lib/urllib/parse.py:1267): a bare dict base, an
# attribute set in __init__, __missing__ storing what it returns, and __repr__ through dict(self).
# A lookup takes the key's type and __missing__'s result for the dict's types. One change: the
# field's annotation (self.safe: frozenset[int]), as Pystachy infers no field's type from a set
# method's result in any class. The safe bytes are given as a list of their ints.

_ALWAYS_SAFE: frozenset[int] = frozenset(b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                         b'abcdefghijklmnopqrstuvwxyz'
                         b'0123456789'
                         b'_.-~')


class _Quoter(dict):
    """A mapping from bytes numbers (in range(0,256)) to strings.

    String values are percent-encoded byte values, unless the key < 128, and
    in either of the specified safe set, or the always safe set.
    """
    # Keeps a cache internally, via __missing__, for efficiency (lookups
    # of cached keys don't call Python code at all).
    def __init__(self, safe):
        """safe: bytes object."""
        self.safe: frozenset[int] = _ALWAYS_SAFE.union(safe)

    def __repr__(self):
        return f"<Quoter {dict(self)!r}>"

    def __missing__(self, b):
        # Handle a cache miss. Store quoted string in cache and return.
        res = chr(b) if b in self.safe else '%{:02X}'.format(b)
        self[b] = res
        return res


q = _Quoter(list(b"/"))
print("".join([q[b] for b in b"a b/c?"]), len(q), sorted(q))
print(q[97], q[32], len(q), 97 in q, 200 in q, q.get(200), len(q))
print(repr(q))
