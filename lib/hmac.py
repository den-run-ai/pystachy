"""HMAC (Keyed-Hashing for Message Authentication) module.

Implements the HMAC algorithm as described by RFC 2104.
"""
# Pystachy's hmac: a subset implementation of CPython 3.13's module over lib/hashlib.py, written
# from RFC 2104. new() and digest() take the hash as its name ("sha256") or as a hashlib
# constructor (hashlib.sha256); the HMAC class takes the name. Keys and messages are bytes.
# compare_digest() compares two bytes or two ASCII strs in time that depends on the second
# one's length only, as CPython's does.

import hashlib as _hashlib

# The size of the digests returned by HMAC depends on the underlying
# hashing module used.  Use digest_size from the instance of HMAC instead.
digest_size = None


def _padded(key: bytes, name: str, size: int, pad: int) -> bytes:
    # the key as RFC 2104 uses it: hashed if it is longer than a block, filled with zeros to
    # the block's size, and each byte combined with pad
    if len(key) > size:
        key = _hashlib.new(name, key).digest()
    out: list[int] = []
    for i in range(size):
        out.append((key[i] if i < len(key) else 0) ^ pad)
    return bytes(out)


class HMAC:
    """RFC 2104 HMAC class.  Also complies with RFC 4231.

    This supports the API for Cryptographic Hash Functions (PEP 247).
    """
    blocksize = 64  # 512-bit HMAC; can be changed in subclasses.

    def __init__(self, key: bytes, msg: bytes | None = None, digestmod: str = "") -> None:
        """Create a new HMAC object.

        key: bytes or buffer, key for the keyed hash object.
        msg: bytes or buffer, Initial input for the hash or None.
        digestmod: A hash name suitable for hashlib.new(). *OR*
                   A hashlib constructor returning a new hash object. *OR*
                   A module supporting PEP 247.

                   Required as of 3.8, despite its position after the optional
                   msg argument.  Passing it as a keyword argument is
                   recommended, though not required for legacy API reasons.
        """
        if digestmod == "":
            raise TypeError("Missing required argument 'digestmod'.")
        self._inner = _hashlib.new(digestmod)
        self._outer = _hashlib.new(digestmod)
        self.digest_size: int = self._inner.digest_size
        self.block_size: int = self._inner.block_size
        self._inner.update(_padded(key, digestmod, self.block_size, 0x36))
        self._outer.update(_padded(key, digestmod, self.block_size, 0x5C))
        if msg is not None:
            self._inner.update(msg)

    @property
    def name(self) -> str:
        return "hmac-" + self._inner.name

    def update(self, msg: bytes) -> None:
        """Feed data from msg into this hashing object."""
        self._inner.update(msg)

    def copy(self) -> "HMAC":
        """Return a separate copy of this hashing object.

        An update to this copy won't affect the original object.
        """
        other = HMAC(b"", None, self._inner.name)
        other._inner = self._inner.copy()
        other._outer = self._outer.copy()
        return other

    def digest(self) -> bytes:
        """Return the hash value of this hashing object.

        This returns the hmac value as bytes.  The object is
        not altered in any way by this function; you can continue
        updating the object after calling this function.
        """
        h = self._outer.copy()
        h.update(self._inner.digest())
        return h.digest()

    def hexdigest(self) -> str:
        """Like digest(), but returns a string of hexadecimal digits instead.
        """
        h = self._outer.copy()
        h.update(self._inner.digest())
        return h.hexdigest()


def _hash_name(digestmod) -> str:
    # the name of the hash that digestmod asks for: a name, or a hashlib constructor's
    if isinstance(digestmod, str):
        return digestmod
    return digestmod().name


def new(key: bytes, msg: bytes | None = None, digestmod="") -> HMAC:
    """Create a new hashing object and return it.

    key: bytes or buffer, The starting key for the hash.
    msg: bytes or buffer, Initial input for the hash, or None.
    digestmod: A hash name suitable for hashlib.new(). *OR*
               A hashlib constructor returning a new hash object. *OR*
               A module supporting PEP 247.

               Required as of 3.8, despite its position after the optional
               msg argument.  Passing it as a keyword argument is
               recommended, though not required for legacy API reasons.

    You can now feed arbitrary bytes into the object using its update()
    method, and can ask for the hash value at any time by calling its digest()
    or hexdigest() methods.
    """
    return HMAC(key, msg, _hash_name(digestmod))


def digest(key: bytes, msg: bytes, digest) -> bytes:
    """Fast inline implementation of HMAC.

    key: bytes or buffer, The key for the keyed hash object.
    msg: bytes or buffer, Input message.
    digest: A hash name suitable for hashlib.new() for best performance. *OR*
            A hashlib constructor returning a new hash object. *OR*
            A module supporting PEP 247.
    """
    return HMAC(key, msg, _hash_name(digest)).digest()


def _same_bytes(a: bytes, b: bytes) -> bool:
    # (as CPython's _tscmp: every byte of b is compared, with a's where the lengths agree)
    result = 0 if len(a) == len(b) else 1
    left = a if len(a) == len(b) else b
    for i in range(len(b)):
        result |= left[i] ^ b[i]
    return result == 0


def compare_digest(a, b) -> bool:
    """Return 'a == b'.

    This function uses an approach designed to prevent
    timing analysis, making it appropriate for cryptography.

    a and b must both be of the same type: either str (ASCII only),
    or any bytes-like object.

    Note: If a and b are of different lengths, or if an error occurs,
    a timing attack could theoretically reveal information about the
    types and lengths of a and b--but not their values.
    """
    if isinstance(a, str) and isinstance(b, str):
        if not a.isascii() or not b.isascii():
            raise TypeError("comparing strings with non-ASCII characters is not supported")
        return _same_bytes(a.encode(), b.encode())
    if isinstance(a, bytes) and isinstance(b, bytes):
        return _same_bytes(a, b)
    raise TypeError("unsupported operand types(s) or combination of types: '%s' and '%s'" % (type(a).__name__, type(b).__name__))
