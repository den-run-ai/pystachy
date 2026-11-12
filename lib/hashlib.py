"""hashlib module - A common interface to many hash functions."""
# Pystachy's hashlib: a subset implementation of CPython 3.13's module, whose hash objects are
# OpenSSL's there. MD5, SHA-1, SHA-224 and SHA-256 are written here from their specifications
# (RFC 1321 and FIPS 180-4), on Pystachy's 64-bit ints: every word is kept below 2**32. The
# constructors and new() take bytes and give one class of hash object, HASH, with update(),
# digest(), hexdigest(), copy(), name, digest_size and block_size. The other algorithms
# (SHA-384 and SHA-512, whose words are 64-bit, SHA-3, BLAKE2), file_digest(), pbkdf2_hmac()
# and scrypt() are not here: algorithms_guaranteed names what is.

__all__ = ["md5", "sha1", "sha224", "sha256", "new", "algorithms_guaranteed", "algorithms_available"]

algorithms_guaranteed = {"md5", "sha1", "sha224", "sha256"}
algorithms_available = {"md5", "sha1", "sha224", "sha256"}

_MD5 = 0
_SHA1 = 1
_SHA224 = 2
_SHA256 = 3
_NAMES = ["md5", "sha1", "sha224", "sha256"]
_SIZES = [16, 20, 28, 32]
_MASK = 0xFFFFFFFF
_HEX = "0123456789abcdef"

# floor(2**32 * abs(sin(i + 1))), and each round's left rotation
_MD5_K = [
    0xD76AA478, 0xE8C7B756, 0x242070DB, 0xC1BDCEEE, 0xF57C0FAF, 0x4787C62A, 0xA8304613, 0xFD469501,
    0x698098D8, 0x8B44F7AF, 0xFFFF5BB1, 0x895CD7BE, 0x6B901122, 0xFD987193, 0xA679438E, 0x49B40821,
    0xF61E2562, 0xC040B340, 0x265E5A51, 0xE9B6C7AA, 0xD62F105D, 0x02441453, 0xD8A1E681, 0xE7D3FBC8,
    0x21E1CDE6, 0xC33707D6, 0xF4D50D87, 0x455A14ED, 0xA9E3E905, 0xFCEFA3F8, 0x676F02D9, 0x8D2A4C8A,
    0xFFFA3942, 0x8771F681, 0x6D9D6122, 0xFDE5380C, 0xA4BEEA44, 0x4BDECFA9, 0xF6BB4B60, 0xBEBFBC70,
    0x289B7EC6, 0xEAA127FA, 0xD4EF3085, 0x04881D05, 0xD9D4D039, 0xE6DB99E5, 0x1FA27CF8, 0xC4AC5665,
    0xF4292244, 0x432AFF97, 0xAB9423A7, 0xFC93A039, 0x655B59C3, 0x8F0CCC92, 0xFFEFF47D, 0x85845DD1,
    0x6FA87E4F, 0xFE2CE6E0, 0xA3014314, 0x4E0811A1, 0xF7537E82, 0xBD3AF235, 0x2AD7D2BB, 0xEB86D391,
]
_MD5_S = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
]
# the first 32 bits of the fractional parts of the cube roots of the first 64 primes
_SHA256_K = [
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
]


def _initial(kind: int) -> list[int]:
    if kind == _MD5:
        return [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476]
    if kind == _SHA1:
        return [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    if kind == _SHA224:
        return [0xC1059ED8, 0x367CD507, 0x3070DD17, 0xF70E5939, 0xFFC00B31, 0x68581511, 0x64F98FA7, 0xBEFA4FA4]
    return [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A, 0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19]


def _md5_block(h: list[int], w: list[int], data: bytes, at: int) -> None:
    # the 64 bytes of data from at, into the state h; w is the caller's 16 words of scratch
    for t in range(16):
        j = at + 4 * t
        w[t] = data[j] | (data[j + 1] << 8) | (data[j + 2] << 16) | (data[j + 3] << 24)
    a = h[0]
    b = h[1]
    c = h[2]
    d = h[3]
    for t in range(64):
        if t < 16:
            f = d ^ (b & (c ^ d))
            g = t
        elif t < 32:
            f = c ^ (d & (b ^ c))
            g = (5 * t + 1) & 15
        elif t < 48:
            f = b ^ c ^ d
            g = (3 * t + 5) & 15
        else:
            f = c ^ (b | (d ^ _MASK))
            g = (7 * t) & 15
        f = (f + a + _MD5_K[t] + w[g]) & _MASK
        s = _MD5_S[t]
        a = d
        d = c
        c = b
        b = (b + ((f << s) | (f >> (32 - s)))) & _MASK
    h[0] = (h[0] + a) & _MASK
    h[1] = (h[1] + b) & _MASK
    h[2] = (h[2] + c) & _MASK
    h[3] = (h[3] + d) & _MASK


def _sha1_block(h: list[int], w: list[int], data: bytes, at: int) -> None:
    # (w: 80 words of scratch)
    for t in range(16):
        j = at + 4 * t
        w[t] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | data[j + 3]
    for t in range(16, 80):
        x = w[t - 3] ^ w[t - 8] ^ w[t - 14] ^ w[t - 16]
        w[t] = ((x << 1) | (x >> 31)) & _MASK
    a = h[0]
    b = h[1]
    c = h[2]
    d = h[3]
    e = h[4]
    for t in range(80):
        if t < 20:
            f = (d ^ (b & (c ^ d))) + 0x5A827999
        elif t < 40:
            f = (b ^ c ^ d) + 0x6ED9EBA1
        elif t < 60:
            f = ((b & c) | (d & (b | c))) + 0x8F1BBCDC
        else:
            f = (b ^ c ^ d) + 0xCA62C1D6
        f = ((((a << 5) | (a >> 27)) & _MASK) + f + e + w[t]) & _MASK
        e = d
        d = c
        c = ((b << 30) | (b >> 2)) & _MASK
        b = a
        a = f
    h[0] = (h[0] + a) & _MASK
    h[1] = (h[1] + b) & _MASK
    h[2] = (h[2] + c) & _MASK
    h[3] = (h[3] + d) & _MASK
    h[4] = (h[4] + e) & _MASK


def _sha256_block(h: list[int], w: list[int], data: bytes, at: int) -> None:
    # (w: 64 words of scratch; a right rotation by n is (x >> n) | (x << (32 - n)), masked)
    for t in range(16):
        j = at + 4 * t
        w[t] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | data[j + 3]
    for t in range(16, 64):
        x = w[t - 15]
        y = w[t - 2]
        s0 = ((x >> 7) | (x << 25)) ^ ((x >> 18) | (x << 14)) ^ (x >> 3)
        s1 = ((y >> 17) | (y << 15)) ^ ((y >> 19) | (y << 13)) ^ (y >> 10)
        w[t] = (w[t - 16] + (s0 & _MASK) + w[t - 7] + (s1 & _MASK)) & _MASK
    a = h[0]
    b = h[1]
    c = h[2]
    d = h[3]
    e = h[4]
    f = h[5]
    g = h[6]
    k = h[7]
    for t in range(64):
        s1 = (((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))) & _MASK
        t1 = k + s1 + (g ^ (e & (f ^ g))) + _SHA256_K[t] + w[t]
        s0 = (((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))) & _MASK
        t2 = s0 + ((a & b) | (c & (a | b)))
        k = g
        g = f
        f = e
        e = (d + t1) & _MASK
        d = c
        c = b
        b = a
        a = (t1 + t2) & _MASK
    h[0] = (h[0] + a) & _MASK
    h[1] = (h[1] + b) & _MASK
    h[2] = (h[2] + c) & _MASK
    h[3] = (h[3] + d) & _MASK
    h[4] = (h[4] + e) & _MASK
    h[5] = (h[5] + f) & _MASK
    h[6] = (h[6] + g) & _MASK
    h[7] = (h[7] + k) & _MASK


def _blocks(kind: int, h: list[int], w: list[int], data: bytes, end: int) -> None:
    # the whole 64-byte blocks of data[:end], into the state h
    at = 0
    if kind == _MD5:
        while at < end:
            _md5_block(h, w, data, at)
            at += 64
    elif kind == _SHA1:
        while at < end:
            _sha1_block(h, w, data, at)
            at += 64
    else:
        while at < end:
            _sha256_block(h, w, data, at)
            at += 64


class HASH:
    """A hash is an object used to calculate a checksum of a string of information.

Methods:

update() -- updates the current digest with an additional string
digest() -- return the current digest value
hexdigest() -- return the current digest as a string of hexadecimal digits
copy() -- return a copy of the current hash object

Attributes:

name -- the hash algorithm being used by this object
digest_size -- number of bytes in this hashes output"""

    def __init__(self, kind: int, data: bytes) -> None:
        self._kind = kind
        self._h = _initial(kind)
        self._w = [0] * (16 if kind == _MD5 else 80 if kind == _SHA1 else 64)
        self._tail = b""  # the bytes after the last whole block: fewer than 64
        self._count = 0  # the bytes hashed
        if len(data) > 0:
            self.update(data)

    @property
    def name(self) -> str:
        return _NAMES[self._kind]

    @property
    def digest_size(self) -> int:
        return _SIZES[self._kind]

    @property
    def block_size(self) -> int:
        return 64

    def update(self, data: bytes, /) -> None:
        """Update this hash object's state with the provided string."""
        self._count += len(data)
        if len(self._tail) > 0:
            data = self._tail + data
        end = len(data) & ~63
        _blocks(self._kind, self._h, self._w, data, end)
        self._tail = data[end:]

    def _final(self) -> list[int]:
        # the state after the padding: a 1 bit, zeros and the count of bits in 8 bytes, to a whole
        # block. This object's own state stays as it is, so that update() may follow digest()
        n = self._count
        pad = [128]
        for _ in range((55 - n) & 63):
            pad.append(0)
        bits = n * 8
        if self._kind == _MD5:
            for i in range(8):
                pad.append((bits >> (8 * i)) & 255)
        else:
            for i in range(8):
                pad.append((bits >> (56 - 8 * i)) & 255)
        last = self._tail + bytes(pad)
        h = list(self._h)
        _blocks(self._kind, h, self._w, last, len(last))
        return h

    def digest(self) -> bytes:
        """Return the digest value as a bytes object."""
        h = self._final()
        out: list[int] = []
        if self._kind == _MD5:
            for x in h:
                out.append(x & 255)
                out.append((x >> 8) & 255)
                out.append((x >> 16) & 255)
                out.append(x >> 24)
        else:
            for i in range(_SIZES[self._kind] // 4):
                x = h[i]
                out.append(x >> 24)
                out.append((x >> 16) & 255)
                out.append((x >> 8) & 255)
                out.append(x & 255)
        return bytes(out)

    def hexdigest(self) -> str:
        """Return the digest value as a string of hexadecimal digits."""
        out: list[str] = []
        for b in self.digest():
            out.append(_HEX[b >> 4])
            out.append(_HEX[b & 15])
        return "".join(out)

    def copy(self) -> "HASH":
        """Return a copy of the hash object."""
        other = HASH(self._kind, b"")
        other._h = list(self._h)
        other._tail = self._tail
        other._count = self._count
        return other


def md5(data: bytes = b"", *, usedforsecurity: bool = True) -> HASH:
    """Returns a md5 hash object; optionally initialized with a string"""
    return HASH(_MD5, data)


def sha1(data: bytes = b"", *, usedforsecurity: bool = True) -> HASH:
    """Returns a sha1 hash object; optionally initialized with a string"""
    return HASH(_SHA1, data)


def sha224(data: bytes = b"", *, usedforsecurity: bool = True) -> HASH:
    """Returns a sha224 hash object; optionally initialized with a string"""
    return HASH(_SHA224, data)


def sha256(data: bytes = b"", *, usedforsecurity: bool = True) -> HASH:
    """Returns a sha256 hash object; optionally initialized with a string"""
    return HASH(_SHA256, data)


def new(name: str, data: bytes = b"", *, usedforsecurity: bool = True) -> HASH:
    """new(name, data=b'') - Return a new hashing object using the named algorithm;
    optionally initialized with data (which must be a bytes-like object).
    """
    lower = name.lower()
    for kind in range(4):
        if _NAMES[kind] == lower:
            return HASH(kind, data)
    raise ValueError("unsupported hash type " + name)
