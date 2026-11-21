import zlib
from zlib import adler32, crc32


print(crc32(b""), adler32(b""), crc32(b"123456789"), adler32(b"Wikipedia"))
data = bytes(range(256)) * 65
for length in [0, 1, 2, 15, 16, 8191, 8192, 8193, len(data)]:
    part = data[:length]
    print(length, zlib.crc32(part), zlib.adler32(part))
for seed in [0, 1, -1, 0xFFFFFFFF, 0xFFFFFFF0, (1 << 40) + 7, -(1 << 63)]:
    print(seed, crc32(b"", seed), adler32(b"", seed), adler32(b"\0", seed))
    print(crc32(data, seed) == crc32(data[17:], crc32(data[:17], seed)))
    print(adler32(data, seed) == adler32(data[17:], adler32(data[:17], seed)))
