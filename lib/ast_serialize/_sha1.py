"""SHA-1 (FIPS 180-4) of bytes, as a lowercase hex digest: the source hash ast_serialize returns
(Pystachy has no hashlib)."""

_HEX = "0123456789abcdef"


def sha1_hex(data: bytes) -> str:
    h0 = 0x67452301
    h1 = 0xEFCDAB89
    h2 = 0x98BADCFE
    h3 = 0x10325476
    h4 = 0xC3D2E1F0
    n = len(data)
    bit_len = n * 8
    tail_len = 64 - (n + 9) % 64
    if tail_len == 64:
        tail_len = 0
    length = [0] * 8
    for i in range(8):
        length[7 - i] = (bit_len >> (8 * i)) & 0xFF
    msg = data + b"\x80" + bytes(tail_len) + bytes(length)
    w = [0] * 80
    mask = 0xFFFFFFFF
    for off in range(0, len(msg), 64):
        for i in range(16):
            j = off + 4 * i
            w[i] = (msg[j] << 24) | (msg[j + 1] << 16) | (msg[j + 2] << 8) | msg[j + 3]
        for i in range(16, 80):
            x = w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16]
            w[i] = ((x << 1) | (x >> 31)) & mask
        a = h0
        b = h1
        c = h2
        d = h3
        e = h4
        for i in range(20):
            t = ((((a << 5) | (a >> 27)) & mask) + ((b & c) | (~b & d)) + e + 0x5A827999 + w[i]) & mask
            e = d
            d = c
            c = ((b << 30) | (b >> 2)) & mask
            b = a
            a = t
        for i in range(20, 40):
            t = ((((a << 5) | (a >> 27)) & mask) + (b ^ c ^ d) + e + 0x6ED9EBA1 + w[i]) & mask
            e = d
            d = c
            c = ((b << 30) | (b >> 2)) & mask
            b = a
            a = t
        for i in range(40, 60):
            t = ((((a << 5) | (a >> 27)) & mask) + ((b & c) | (b & d) | (c & d)) + e + 0x8F1BBCDC + w[i]) & mask
            e = d
            d = c
            c = ((b << 30) | (b >> 2)) & mask
            b = a
            a = t
        for i in range(60, 80):
            t = ((((a << 5) | (a >> 27)) & mask) + (b ^ c ^ d) + e + 0xCA62C1D6 + w[i]) & mask
            e = d
            d = c
            c = ((b << 30) | (b >> 2)) & mask
            b = a
            a = t
        h0 = (h0 + a) & mask
        h1 = (h1 + b) & mask
        h2 = (h2 + c) & mask
        h3 = (h3 + d) & mask
        h4 = (h4 + e) & mask
    out: list[str] = []
    for h in (h0, h1, h2, h3, h4):
        for k in range(28, -4, -4):
            out.append(_HEX[(h >> k) & 15])
    return "".join(out)
