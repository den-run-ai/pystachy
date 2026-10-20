# pyaes's AES block cipher, both ways: the known answers of FIPS-197 Appendix C (the key
# 00 01 02 ... for each key size) and of NIST SP 800-38A F.1 (ECB, four blocks for each key
# size, with the keys whose expansion FIPS-197 Appendix A lists), chains of blocks there and
# back, keys whose words are at the edges of a signed 32-bit int, blocks of ints outside
# 0..255 (up to the edges of a 64-bit int), a key changed after use, counter mode and
# Telethon's AES-IGE built on the cipher, and the errors for wrong key and block sizes.
# One program, as each AOT build of pyaes's tables takes seconds.
# The key is a list of ints here, where upstream takes bytes (ports/pyaes predates Pystachy's bytes).
import pyaes
from pyaes import AES


def unhex(s: str) -> list[int]:
    return [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]


def hx(xs: list[int]) -> str:
    return "".join(["%02x" % b for b in xs])


def words(ws: list[int]) -> str:
    return " ".join(["%08x" % (w & 0xFFFFFFFF) for w in ws])


# FIPS-197 Appendix C.1, C.2 and C.3
pt = unhex("00112233445566778899aabbccddeeff")
for n, want in [(16, "69c4e0d86a7b0430d8cdb78070b4c55a"), (24, "dda97ca4864cdfe06eaf70a0ec0d7191"),
                (32, "8ea2b7ca516745bfeafc49904b496089")]:
    aes = pyaes.AES(list(range(n)))
    ct = aes.encrypt(pt)
    print("C", n * 8, len(aes._Ke) - 1, "rounds:", hx(ct), hx(ct) == want, aes.decrypt(ct) == pt)

# NIST SP 800-38A F.1.1 to F.1.6; the key's words as struct.unpack('>i') reads them (signed),
# and the last round key of FIPS-197 Appendix A.1 to A.3
PT = ["6bc1bee22e409f96e93d7e117393172a", "ae2d8a571e03ac9c9eb76fac45af8e51",
      "30c81c46a35ce411e5fbc1191a0a52ef", "f69f2445df4f9b17ad2b417be66c3710"]
CASES = [
    ("2b7e151628aed2a6abf7158809cf4f3c", "d014f9a8 c9ee2589 e13f0cc8 b6630ca6",
     ["3ad77bb40d7a3660a89ecaf32466ef97", "f5d3d58503b9699de785895a96fdbaaf",
      "43b1cd7f598ece23881b00e3ed030688", "7b0c785e27e8ad3f8223207104725dd4"]),
    ("8e73b0f7da0e6452c810f32b809079e562f8ead2522c6b7b", "e98ba06f 448c773c 8ecc7204 01002202",
     ["bd334f1d6e45f25ff712a214571fa5cc", "974104846d0ad3ad7734ecb3ecee4eef",
      "ef7afd2270e2e60adce0ba2face6444e", "9a4b41ba738d6c72fb16691603c18e0e"]),
    ("603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4",
     "fe4890d1 e6188d0b 046df344 706c631e",
     ["f3eed1bdb5d2a03c064b5a7e3db181f8", "591ccb10d410ed26dc5ba74a31362870",
      "b6ed21b99ca6f4f9f153e7b1beafed1d", "23304b7a39f9f3ff067d8d8f9e24ecc7"]),
]
for key, last, cts in CASES:
    aes = AES(unhex(key))
    print("A", len(key) * 4, aes._Ke[0], words(aes._Ke[-1]) == last, aes._Kd[0] == aes._Ke[-1])
    for i in range(4):
        got = aes.encrypt(unhex(PT[i]))
        back = aes.decrypt(unhex(cts[i]))
        print("F.1", len(key) * 4, i + 1, hx(got), hx(got) == cts[i], hx(back) == PT[i])

# a block encrypted 20 times over, then decrypted 20 times back
for n in [16, 24, 32]:
    for fill in [0, 0xFF, 0x80]:
        aes = AES([(fill + 37 * i) & 0xFF for i in range(n)])
        block = [fill] * 16
        for r in range(20):
            block = aes.encrypt(block)
        print(n, fill, hx(block))
        for r in range(20):
            block = aes.decrypt(block)
        print(n, fill, block == [fill] * 16)

# keys whose words read as -1, -2139062144, 2**31 - 1, -2**31 and 0
for edge_key in [[0xFF] * 32, [0x80] * 24, [0x7F, 0xFF, 0xFF, 0xFF] * 4, [0x80, 0, 0, 0] * 4,
                 [0] * 16]:
    aes = AES(edge_key)
    print(len(edge_key), aes._Ke[0], hx(aes.encrypt([0xFF] * 16)), hx(aes.decrypt([0] * 16)))

# ints outside 0..255 in a block (upstream's modes pass it bytes; the cipher takes any ints)
aes = AES([0] * 16)
block = [256, -1] * 8
print(aes.encrypt(block), block)
print(aes.encrypt([2 ** 31] * 16))
print(aes.decrypt([2 ** 39 - 1, -129] * 8))
# and at the edges of a 64-bit int, where _compact_word's shifts of them still fit
for blk in [[0, 0, 0, 9223372036854775807] * 4, [0, 0, 0, -9223372036854775807 - 1] * 4,
            [0, 0, 2 ** 55 - 1, 0] * 4, [0, -2 ** 47 + 0x1234, 0, 0] * 4,
            [-2 ** 39 + 0x5A, 0, 0, 0] * 4]:
    print(aes.encrypt(blk)[:6], aes.decrypt(blk)[:6])

# the key is read, not kept: changing the list afterwards changes nothing
key16 = list(range(16))
aes = AES(key16)
before = aes.encrypt([0] * 16)
key16[0] = 0xFF
print(aes.encrypt([0] * 16) == before)


# counter mode by hand, as AESModeOfOperationCTR does it with its default Counter (from 1)
def ctr(aes: AES, data: list[int]) -> list[int]:
    out: list[int] = []
    stream: list[int] = []
    counter = 1
    for i in range(len(data)):
        if i % 16 == 0:
            stream = aes.encrypt([0] * 8 + [(counter >> (56 - 8 * j)) & 0xFF for j in range(8)])
            counter += 1
        out.append(data[i] ^ stream[i % 16])
    return out


# the example of pyaes's README.md, whose ciphertext it lists
aes = AES([ord(c) for c in "This_key_for_demo_purposes_only!"])
text = "Text may be any length you wish, no padding is required"
ct = ctr(aes, [ord(c) for c in text])
print(len(ct), hx(ct))
print("".join([chr(b) for b in ctr(aes, ct)]))


# AES-IGE as Telethon builds it on pyaes.AES (telethon/crypto/aes.py), whose decrypt passes the
# same list for every block, on the IGE test vector of OpenSSL's test/igetest.c
def encrypt_ige(plain: list[int], key: list[int], iv: list[int]) -> list[int]:
    iv1 = iv[:16]
    iv2 = iv[16:]
    aes = AES(key)
    out: list[int] = []
    for b in range(len(plain) // 16):
        block = list(plain[b * 16:b * 16 + 16])
        for i in range(16):
            block[i] ^= iv1[i]
        c = aes.encrypt(block)
        for i in range(16):
            c[i] ^= iv2[i]
        iv1 = c
        iv2 = plain[b * 16:b * 16 + 16]
        out.extend(c)
    return out


def decrypt_ige(cipher: list[int], key: list[int], iv: list[int]) -> list[int]:
    iv1 = iv[:16]
    iv2 = iv[16:]
    aes = AES(key)
    out: list[int] = []
    block = [0] * 16
    for b in range(len(cipher) // 16):
        for i in range(16):
            block[i] = cipher[b * 16 + i] ^ iv2[i]
        p = aes.decrypt(block)
        for i in range(16):
            p[i] ^= iv1[i]
        iv1 = cipher[b * 16:b * 16 + 16]
        iv2 = p
        out.extend(p)
    return out


ct = encrypt_ige([0] * 32, list(range(16)), list(range(32)))
print("IGE", hx(ct), hx(ct) == "1a8519a6557be652e9da8e43da4ef4453cf456b4ca488aa383c79c98b34797cb",
      decrypt_ige(ct, list(range(16)), list(range(32))) == [0] * 32)
msg = [ord(c) for c in "The quick brown fox jumps over the lazy dog, twice."[:48]]
ct = encrypt_ige(msg, list(range(32)), [0xA5] * 32)
print("IGE", len(ct), hx(ct[32:]), decrypt_ige(ct, list(range(32)), [0xA5] * 32) == msg)

for bad in [0, 15, 17, 33]:
    try:
        AES([0] * bad)
        print("key", bad, "no error")
    except ValueError as e:
        print("key", bad, "ValueError:", e)
aes = AES([1] * 16)
for bad in [0, 15, 17]:
    try:
        aes.encrypt([0] * bad)
        print("encrypt", bad, "no error")
    except ValueError as e:
        print("encrypt", bad, "ValueError:", e)
    try:
        aes.decrypt([0] * bad)
        print("decrypt", bad, "no error")
    except ValueError as e:
        print("decrypt", bad, "ValueError:", e)
