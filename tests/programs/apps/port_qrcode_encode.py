# qrcode's headline API, QRCode(...).add_data(text); make(); print_ascii(), on codes of each
# data mode (numeric, alphanumeric, bytes, also UTF-8 of non-ASCII text), error correction
# level and mask, at versions 1 to 7; then its errors (the checks of QRCode's arguments and of
# its version and mask_pattern setters, data too long), get_matrix(), the version fit across
# the three sizes of the length fields, the chunk optimizer (util.optimal_data_chunks) and
# util.QRData segments passed to add_data()
import sys

import qrcode
from qrcode import constants
from qrcode import exceptions
from qrcode import util


def show(data: str, ec: int, border: int, invert: bool) -> None:
    qr = qrcode.QRCode(error_correction=ec, border=border)
    qr.add_data(data)
    qr.make()
    # the bytes as the library counts them: len(data) counts characters in CPython and
    # UTF-8 bytes in Pystachy, a documented deviation
    nbytes = sum([len(c) for c in qr.data_list])
    print(f"== {nbytes} bytes, modes {[c.mode for c in qr.data_list]}, ec {ec}, border {border}")
    qr.print_ascii(out=sys.stdout, invert=invert)
    print("version", qr.version, "size", qr.modules_count)


def digest(qr: qrcode.QRCode) -> str:
    # the modules of a code, as a checksum
    dark = 0
    h = 0
    for row in qr.modules:
        for cell in row:
            h = (h * 31 + (1 if cell else 0)) % 1000000007
            if cell:
                dark += 1
    return f"version {qr.version} size {qr.modules_count} dark {dark} hash {h}"


def code(data: str, ec: int, mask: int | None = None) -> str:
    qr = qrcode.QRCode(error_correction=ec, mask_pattern=mask)
    qr.add_data(data)
    qr.make()
    return f"{[c.mode for c in qr.data_list]} {digest(qr)}"


def chunks(data: str, minimum: int) -> str:
    return " ".join([f"{c.mode}:{len(c)}" for c in util.optimal_data_chunks(data, minimum=minimum)])


show("HELLO WORLD", constants.ERROR_CORRECT_Q, 1, False)  # alphanumeric
show("01234567890123456789", constants.ERROR_CORRECT_L, 0, True)  # numeric, inverted
show("https://example.com/\u043f\u0443\u0442\u044c?q=\u20ac", constants.ERROR_CORRECT_H, 1, False)  # UTF-8
print("empty", code("", constants.ERROR_CORRECT_M))
print("mixed", code("ABC" + "1" * 30 + "abc" + "XYZ" * 8, constants.ERROR_CORRECT_M))
print("CJK", code("\u65e5\u672c\u8a9e \U0001f600 QR", constants.ERROR_CORRECT_Q))
# version 7 and up carry the version in two blocks of 18 modules (a mask given: choosing one
# makes the code 9 times, which is slow where the gc-stress tests collect at every allocation)
print("v7", code("The quick brown fox jumps over the lazy dog. " * 3 + "\u00e9" * 8,
                 constants.ERROR_CORRECT_L, 3))
# each mask, given, without fitting
for mask in range(8):
    qr = qrcode.QRCode(version=1, mask_pattern=mask)
    qr.add_data("12345")
    qr.make(fit=False)
    print("mask", mask, digest(qr))

# QRCode()'s checks, also with the extreme 64-bit ints
for v in [41, 0, -1, 9223372036854775807, -9223372036854775807 - 1]:
    try:
        qrcode.QRCode(version=v)
    except ValueError as e:
        print("version:", e)
for m in [8, -1]:
    try:
        qrcode.QRCode(mask_pattern=m)
    except ValueError as e:
        print("mask_pattern:", e)
for b in [0, -9223372036854775807]:
    try:
        qrcode.QRCode(box_size=b)
    except ValueError as e:
        print("box_size:", e)
try:
    qrcode.QRCode(border=-1)
except ValueError as e:
    print("border:", e)
# image_factory is the fifth parameter, and mask_pattern the sixth
try:
    qrcode.QRCode(None, constants.ERROR_CORRECT_M, 10, 4, 5)
except TypeError as e:
    print("image_factory:", e)
qr = qrcode.QRCode(2, constants.ERROR_CORRECT_H, 10, 0, None, 5)
qr.add_data("PYSTACHY")
qr.make(fit=False)
print("positional", qr.mask_pattern, digest(qr))

# what the setters of version and mask_pattern check
qr = qrcode.QRCode()
qr.add_data("123")
try:
    qr.mask_pattern = 9
    qr.make()
except ValueError as e:
    print("mask_pattern = 9:", e)
for v in [41, 0, -1]:
    qr = qrcode.QRCode()
    qr.add_data("123")
    try:
        qr.version = v
        qr.make(fit=False)
    except ValueError as e:
        print(f"version = {v}:", e)
qr = qrcode.QRCode()
qr.add_data("123")
qr.version = 3
qr.mask_pattern = 2
qr.make(fit=False)
print("set before make:", qr.version, qr.mask_pattern, qr.modules_count)

# data too long: for the version given, and for any version (the version setter's error)
qr = qrcode.QRCode(version=1, error_correction=constants.ERROR_CORRECT_H)
qr.add_data("this text is far too long for a version 1 symbol")
try:
    qr.make(fit=False)
except exceptions.DataOverflowError as e:
    print("DataOverflowError:", e)
for n in [2953, 2954]:
    qr = qrcode.QRCode(error_correction=constants.ERROR_CORRECT_L)
    qr.add_data("a" * n)
    try:
        print(n, "bytes fit version", qr.best_fit())
    except ValueError as e:
        print(n, "bytes:", e)
qr = qrcode.QRCode(error_correction=5)
qr.add_data("x")
try:
    qr.make()
except IndexError as e:
    print("error_correction 5:", e)

# the version fit: the length fields grow at versions 10 and 27, and best_fit() tries again
for data in ["9" * 235, "9" * 236, "A" * 143, "A" * 144, "z" * 98, "z" * 99, "z" * 593, "z" * 594,
             "\u65e5\u672c" * 16]:
    qr = qrcode.QRCode(error_correction=constants.ERROR_CORRECT_H)
    qr.add_data(data)
    print("fit", chunks(data, 20), "version", qr.best_fit())

# print_ascii(tty=True) needs a terminal
qr = qrcode.QRCode(version=1)
qr.add_data("tty")
try:
    qr.print_ascii(out=sys.stdout, tty=True)
except OSError as e:
    print("OSError:", e)

# test_add_qrdata: a QRData of the data's chosen mode, added as it is
qr = qrcode.QRCode(version=1, border=1)
qr.add_data(util.QRData("a"))
qr.add_data(util.QRData("12", mode=util.MODE_8BIT_BYTE))
qr.make(fit=False)
print("qrdata", [len(d) for d in qr.data_list], [d.mode for d in qr.data_list], sum([row.count(True) for row in qr.modules]))

# get_matrix(): the border is added, its rows are one list, and without it are the modules
qr = qrcode.QRCode(border=2, mask_pattern=1)
qr.add_data("HELLO world 2026")
matrix = qr.get_matrix()
print("matrix", len(matrix), len(matrix[0]), matrix[0][0], matrix[2][2], matrix[3][3],
      sum([row.count(True) for row in matrix]))
matrix[0][0] = True
print("aliasing", matrix[1][0], matrix[len(matrix) - 1][0], matrix[len(matrix) - 2][0])
qr.border = 0
print("no border", len(qr.get_matrix()), qr.get_matrix() is qr.modules)

# two add_data() calls, and make() again after a third; make(fit=False) without a version
qr = qrcode.QRCode(border=0, mask_pattern=6)
qr.add_data("HELLO ")
qr.add_data("world 2026")
qr.make()
print("two adds", [c.mode for c in qr.data_list], qr.version, qr.data_cache is not None)
qr.add_data("0123456789" * 5)
print("data_cache after add_data:", qr.data_cache)
qr.make()
print("re-make", [c.mode for c in qr.data_list], digest(qr))
qr = qrcode.QRCode(mask_pattern=4)
qr.add_data("fit=False without a version")
qr.make(fit=False)
print("fit=False", qr.version)

# the chunk optimizer: runs of digits, then of alphanumerics, at least `minimum` bytes long;
# data of at most `minimum` bytes is one chunk if it is all of one class, up to a final "\n"
for s in ["", "1", "12", "A", "a", "123\n", "1234\n5", "HELLO\n\n", "\n", "12345\n6", "HELLO WORLD\n",
          "\u20ac12345678901234567890123\u20acABCDEFGHIJKLMNOPQRSTUVWXYZ\u20ac",
          "a\x00b\x00" + "9" * 40 + "\U0001f600" * 3, "\u65e5\u672c\u8a9e\u30c6\u30ad\u30b9\u30c8 \U0001f600 QR",
          "ABC" + "1" * 30 + "abc" + "XYZ" * 10 + "~", "e\u0301\u0301 123456"]:
    print(repr(s), "|", chunks(s, 1), "|", chunks(s, 4), "|", chunks(s, 20), "|",
          util.optimal_mode(util.to_bytestring(s)))
# a negative minimum makes upstream's regexes end in the literal text "{-1,}", not a repeat:
# a chunk is one character of the class followed by that text
print("minimum -1:", chunks("a12345bcd", -1), "|", chunks("12", -1), "|", chunks("", -1), "|",
      chunks("x5{-1,}yA{-1,}{-1,}", -1), "|", chunks("1{-2,}B{-2,}", -2), "|", chunks("A{-1,}", -2))
qr = qrcode.QRCode(mask_pattern=0)
qr.add_data("zzA{-1,}", optimize=-1)
qr.make()
print("optimize -1:", [c.mode for c in qr.data_list], digest(qr))
# pseudo-random strings of runs of each class (lists of characters: indexing a str counts
# UTF-8 bytes in Pystachy, a documented deviation)
CLASSES = [list("0123456789"), list("ABCXYZ $%*+-./:"), list("abc~\n"), ["\u00e9", "\u20ac", "\U0001f600"]]
seed = 2026


def rand(n: int) -> int:
    global seed
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed // 65536 % n


total = 0
for _ in range(60):
    s = ""
    for _ in range(rand(9)):
        alphabet = CLASSES[rand(4)]
        for _ in range(rand(13)):
            s += alphabet[rand(len(alphabet))]
    for minimum in [1, 3, 7]:
        total += len(list(util.optimal_data_chunks(s, minimum=minimum)))
    print(chunks(s, 3))
print("chunks", total)
print("optimal_mode", [util.optimal_mode(util.to_bytestring(s)) for s in ["", "0", "\u0663", "A1 $", "a", "\u00bd"]])
