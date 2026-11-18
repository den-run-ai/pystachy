# error: argument must be read-write bytes-like object, not bytes
import struct

struct.pack_into("<I", b"abcd", 0, 1)
