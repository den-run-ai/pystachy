# My own native check: parse the files named in list.txt, and a damaged copy of each, and print
# lengths, CRC-32s and the first error
import binascii

from ast_serialize import parse


def show(name: str, src: bytes) -> None:
    for skip in [False, True]:
        r = parse(name, src, skip, (3, 11), "linux", [], [], 5)
        first = ""
        for e in r[1]:
            first = str(e["line"]) + ":" + str(e["column"]) + ":" + str(e["message"])
            break
        print(name, skip, len(r[0]), binascii.crc32(r[0]), len(r[3]), binascii.crc32(r[3]), len(r[1]), first, len(r[2]))


with open("list.txt") as f:
    names = [line.strip() for line in f if line.strip()]
for n, name in enumerate(names):
    with open(name, "rb") as g:
        src = g.read()
    show(name, src)
    k = (len(src) * 7 + n * 131) % (len(src) + 1)
    show(name, src[:k] + b") lambda: (" + src[k:])
    show(name, src[: len(src) // 2])
