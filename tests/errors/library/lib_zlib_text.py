# error: lib_zlib_text.py:4: error: expected bytes, got str
import zlib

print(zlib.adler32("checksum"))
