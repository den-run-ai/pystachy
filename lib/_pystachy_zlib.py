"""The byte checksum functions of zlib."""
from binascii import crc32 as _crc32


def crc32(data: bytes, value: int = 0, /) -> int:
    return _crc32(data, value)


def adler32(data: bytes, value: int = 1, /) -> int:
    low = value & 0xffff
    high = (value >> 16) & 0xffff
    if len(data) == 1:
        # libz's one-byte path subtracts the modulus once per half, including
        # when the caller supplies an initial pair outside the usual range.
        low += data[0]
        if low >= 65521:
            low -= 65521
        high += low
        if high >= 65521:
            high -= 65521
        return (high << 16) | low

    # Reduce periodically so that both sums fit even a signed 64-bit int.
    for start in range(0, len(data), 8192):
        for i in range(start, min(start + 8192, len(data))):
            low += data[i]
            high += low
        low %= 65521
        high %= 65521
    return ((high % 65521) << 16) | (low % 65521)
