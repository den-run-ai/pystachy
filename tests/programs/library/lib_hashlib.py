# hashlib (lib/hashlib.py): MD5, SHA-1, SHA-224 and SHA-256 give the digests of CPython's
# (OpenSSL's) hash objects: the specifications' test messages, every length around the block and
# padding boundaries, updates in pieces, digests between updates, copies, new() by name, and the
# objects' name, digest_size and block_size
import hashlib


def message(n: int, seed: int) -> bytes:
    out: list[int] = []
    x = seed
    for _ in range(n):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        out.append((x >> 16) & 255)
    return bytes(out)


NAMES = ["md5", "sha1", "sha224", "sha256"]

# the specifications' messages
for text in [b"", b"a", b"abc", b"message digest", b"abcdefghijklmnopqrstuvwxyz",
             b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
             b"abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
             b"The quick brown fox jumps over the lazy dog"]:
    print(len(text), hashlib.md5(text).hexdigest())
    print(len(text), hashlib.sha1(text).hexdigest())
    print(len(text), hashlib.sha224(text).hexdigest())
    print(len(text), hashlib.sha256(text).hexdigest())
million = b"a" * 1000000
print(hashlib.md5(million).hexdigest())
print(hashlib.sha1(million).hexdigest())
print(hashlib.sha224(million).hexdigest())
print(hashlib.sha256(million).hexdigest())

# every length from 0 to 300 bytes, and some longer ones: a digest of all the digests
for name in NAMES:
    total = hashlib.new(name)
    for n in list(range(301)) + [511, 512, 513, 1023, 1024, 4095, 4096, 4097, 65537]:
        total.update(hashlib.new(name, message(n, n + 1)).digest())
    print(name, "lengths", total.hexdigest())

# updates in pieces of every size give the digest of the whole; a digest between updates and a
# copy leave the object as it was
data = message(1500, 7)
for name in NAMES:
    whole = hashlib.new(name, data).hexdigest()
    same = 0
    for step in [1, 2, 3, 5, 7, 31, 32, 33, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 1499, 1500, 2000]:
        h = hashlib.new(name)
        at = 0
        between = 0
        while at < len(data):
            h.update(data[at:at + step])
            at += step
            if at == 3 * step:
                between = len(h.digest()) + len(h.hexdigest())
                other = h.copy()
                other.update(b"more")
                between += len(other.hexdigest())
        if h.hexdigest() == whole and (between == 0 or between == 5 * h.digest_size):
            same += 1
    print(name, "pieces", same, whole)

# the attributes, new() by name, keywords and the digest's forms
for name in NAMES:
    h = hashlib.new(name)
    print(h.name, h.digest_size, h.block_size, len(h.digest()), len(h.hexdigest()), name in hashlib.algorithms_guaranteed,
          name in hashlib.algorithms_available)
print(hashlib.new("SHA256", b"abc").name, hashlib.new("Md5").hexdigest())
print(hashlib.new("sha1", b"abc", usedforsecurity=False).hexdigest() == hashlib.sha1(b"abc").hexdigest())
print(hashlib.sha256(data=b"abc").hexdigest() == hashlib.sha256(b"abc", usedforsecurity=False).hexdigest())
print(hashlib.md5(b"abc").digest().hex(), hashlib.md5(b"abc").digest() == bytes.fromhex(hashlib.md5(b"abc").hexdigest()))
h = hashlib.sha1()
print(h.update(b"abc"), h.hexdigest(), h.hexdigest())
h.update(b"")
c = h.copy()
h.update(b"def")
print(c.hexdigest() == hashlib.sha1(b"abc").hexdigest(), h.hexdigest() == hashlib.sha1(b"abcdef").hexdigest(), c.name)
for name in ["sha1024", "sha 1", "none"]:
    try:
        hashlib.new(name)
    except ValueError as e:
        print("ValueError:", e)


# what mypy.util does with a file's contents
def hash_digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def hash_digest_bytes(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()


print(hash_digest(b"import os\n"), hash_digest_bytes(b"import os\n").hex())
