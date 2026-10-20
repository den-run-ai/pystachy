# binascii: lib/_pystachy_binascii.py, the stand-in Pystachy loads for CPython's C module
# (Modules/binascii.c), against that module: hex with separators, base64 (strict mode and its
# errors), uu, quoted-printable (text, binary, header and tab modes, soft line breaks, CRLF
# text), crc32 and crc_hqx (incremental, masked start values), str arguments of the a2b_*()
# functions, keyword arguments, round trips of all 256 byte values, and binascii.Error and
# binascii.Incomplete
import binascii


def hx(data: bytes, sep: str, n: int) -> None:
    try:
        print(binascii.hexlify(data, sep, n))
    except ValueError as e:
        print("ValueError:", e)
    except OverflowError as e:
        print("OverflowError:", e)


def unhex(s: bytes) -> None:
    try:
        print(binascii.unhexlify(s))
    except binascii.Error as e:
        print("Error:", e)


def a64(s: bytes, strict: bool) -> None:
    try:
        print(binascii.a2b_base64(s, strict_mode=strict))
    except binascii.Error as e:
        print("Error:", e)


def auu(s: bytes) -> None:
    try:
        print(binascii.a2b_uu(s))
    except binascii.Error as e:
        print("Error:", e)


def qp(data: bytes) -> None:
    print(binascii.b2a_qp(data), binascii.b2a_qp(data, quotetabs=True), binascii.b2a_qp(data, istext=False),
          binascii.b2a_qp(data, header=True))


print(binascii.__name__, binascii.__doc__)
print(repr(binascii.Error("x")), repr(binascii.Incomplete()), str(binascii.Error("bad")))

print("hex")
data = b"\x01\x02\x03\x04\x05"
print(binascii.hexlify(data), binascii.b2a_hex(b"\xb9\x01\xef"), binascii.hexlify(b""))
for n in [1, 2, 3, -1, -2, -3, 0, 5, 6, 100, -100]:
    print(n, binascii.hexlify(data, "-", n), binascii.b2a_hex(data, b":", n))
print(binascii.hexlify(data=b"ab", sep=" ", bytes_per_sep=1), binascii.hexlify(b"", ":", 2))
for sep in ["", "--", "é", "Ā", "?"]:
    hx(b"abc", sep, 1)
hx(b"abc", "-", 2**31)
for t in [b"0102ff", b"0102FF", b"", b"010", b"01x2", b"0g", b" 0"]:
    unhex(t)
print(binascii.a2b_hex("4142"), binascii.unhexlify("ffFF"))
try:
    binascii.unhexlify("é0")
except ValueError as e:
    print("ValueError:", e)

print("base64")
for n in range(7):
    print(binascii.b2a_base64(b"hello!"[:n]), binascii.b2a_base64(b"\xff\xfe\xfd"[: n % 4], newline=False))
for t in [b"aGVsbG8=", b"aGVsbG8", b"aGVsbG8==", b"aGVs\nbG8=\n", b"a!G@V#s$", b"=aGVs", b"aGVsbA==",
          b"aGVsbA=", b"aGVsbA", b"aGVsb", b"aGVsbA==x", b"aGV=sbA==", b"aG==Vs", b"YQ==YQ==", b"", b"====",
          b"a", b"ab=c", b"abc=", b"abcd=", b"ab==", b"ab==="]:
    a64(t, False)
    a64(t, True)
print(binascii.a2b_base64("aGVsbG8="), binascii.a2b_base64(b"aGVsbG8=", strict_mode=False))

print("crc")
print(binascii.crc32(b""), binascii.crc32(b"hello"), binascii.crc32(b"hello", 1), binascii.crc32(b"world", binascii.crc32(b"hello ")),
      binascii.crc32(b"hello world"))
print(binascii.crc32(b"abc", -1), binascii.crc32(b"abc", 2**32 + 5), binascii.crc32(b"abc", 0xFFFFFFFF))
print(binascii.crc_hqx(b"", 0), binascii.crc_hqx(b"hello", 0), binascii.crc_hqx(b"hello", 0xFFFF),
      binascii.crc_hqx(b"world", binascii.crc_hqx(b"hello ", 0)), binascii.crc_hqx(b"hello world", 0),
      binascii.crc_hqx(b"abc", -1), binascii.crc_hqx(b"abc", 2**20 + 3))

print("uu")
for t in [b"", b"a", b"ab", b"abc", b"\x00\x00\x00", b"x" * 45]:
    print(binascii.b2a_uu(t), binascii.b2a_uu(t, backtick=True))
try:
    binascii.b2a_uu(b"x" * 46)
except binascii.Error as e:
    print("Error:", e)
for t in [b"#86)C\n", b"#86)C", b"#86)C  `\r\n", b"#86", b"", b" ", b"`", b"!", b"#86)C!", b"#8\x7f)C",
          b"$86)C", b"#86)C\n\n"]:
    auu(t)
print(binascii.a2b_uu("#86)C\n"))

print("qp")
for t in [b"", b"hello", b"a=b", b"tab\tand space \nnext", b"end space ", b"end tab\t", b".\n", b"..\n",
          b"a.\n.b", b"under_score", b"\x00\x7f\x80\xff", b"crlf\r\nline\r\n", b"lf\nthen\r\ncrlf", b"cr\ronly",
          b"x" * 80, b"y" * 75 + b"\n" + b"z" * 76, b"=" * 30, b"a b" * 30, b"line \r\n", b"lone\r"]:
    qp(t)
for t in [b"a=3Db", b"a=3db", b"soft=\nbreak", b"soft=\r\nbreak", b"soft=  \nbreak", b"bad=xy", b"end=",
          b"==41", b"=4", b"a_b", b"=\r", b"x=\rrest\ny"]:
    print(binascii.a2b_qp(t), binascii.a2b_qp(t, header=True))
print(binascii.a2b_qp("a=3Db"), binascii.a2b_qp(data=b"a_b", header=True))

print("round trips")
allb = bytes(range(256))
print(binascii.unhexlify(binascii.hexlify(allb)) == allb, binascii.a2b_base64(binascii.b2a_base64(allb)) == allb,
      binascii.a2b_qp(binascii.b2a_qp(allb, istext=False)) == allb)
uu = b""
for i in range(0, 256, 45):
    uu = uu + binascii.a2b_uu(binascii.b2a_uu(allb[i : i + 45]))
print(uu == allb, len(binascii.b2a_qp(allb)), binascii.crc32(allb), binascii.crc_hqx(allb, 0))
print(binascii.b2a_base64(allb))
print(binascii.b2a_qp(allb))
try:
    raise binascii.Incomplete("more")
except binascii.Incomplete as e:
    print("Incomplete:", e)
try:
    binascii.a2b_base64(b"abc", strict_mode=True)
except ValueError as e:
    # (binascii.Error is a ValueError)
    print("ValueError:", type(e).__name__, e)
try:
    binascii.unhexlify(b"0")
except Exception as e:
    print("Exception:", type(e).__name__, e)
