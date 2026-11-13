# parse() with a source typed str | None, as a caller that may let it read the file passes it
import binascii
import sys

from ast_serialize import parse


def tree(path: str, source: str | None) -> bytes:
    return parse(path, source, False, (3, 13), "linux", None, None, 5)[0]


print(binascii.crc32(tree("m.py", "x = 1\n")))
print(binascii.crc32(tree(sys.argv[0], None)) != 0)
