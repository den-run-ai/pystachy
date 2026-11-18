# hmac over lib/hashlib: RFC 2202 and RFC 4231 test cases, update() and copy(), the hash given as
# a name or as a hashlib constructor, hmac.digest() and compare_digest().
import hashlib
import hmac

# RFC 2202 (MD5, SHA-1) and RFC 4231 (SHA-224, SHA-256) test cases 1, 2, 3, 6 and 7
CASES = [
    (b"\x0b" * 20, b"Hi There"),
    (b"Jefe", b"what do ya want for nothing?"),
    (b"\xaa" * 20, b"\xdd" * 50),
    (b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First"),
    (b"\xaa" * 131, b"This is a test using a larger than block-size key and a larger than block-size data. The key needs to be hashed before being used by the HMAC algorithm."),
]
for key, msg in CASES:
    for name in ["md5", "sha1", "sha224", "sha256"]:
        h = hmac.new(key, msg, name)
        print(name, h.hexdigest(), h.name, h.digest_size, h.block_size)
h = hmac.new(b"key", digestmod=hashlib.sha256)
h.update(b"The quick brown fox ")
c = h.copy()
h.update(b"jumps over the lazy dog")
print(h.hexdigest())
print(c.hexdigest(), c.digest() == hmac.new(b"key", b"The quick brown fox ", "sha256").digest())
print(hmac.new(b"key", b"The quick brown fox jumps over the lazy dog", hashlib.md5).hexdigest())
print(hmac.new(b"key", b"The quick brown fox jumps over the lazy dog", digestmod=hashlib.sha1).hexdigest())
print(hmac.digest(b"key", b"message", "sha256").hex(), hmac.digest(b"key", b"message", hashlib.sha224).hex())
print(hmac.HMAC(b"k" * 64, b"", "SHA256").hexdigest(), hmac.HMAC(b"k" * 65, None, "sha1").hexdigest())
print(hmac.new(b"", b"", "md5").hexdigest(), hmac.digest_size)
a = hmac.new(b"secret", b"payload", "sha256").digest()
print(hmac.compare_digest(a, hmac.new(b"secret", b"payload", "sha256").digest()), hmac.compare_digest(a, a[:-1]), hmac.compare_digest(a, b""), hmac.compare_digest(b"", b""))
print(hmac.compare_digest("abc", "abc"), hmac.compare_digest("abc", "abd"), hmac.compare_digest("abc", "ab"), hmac.compare_digest("", ""))
try:
    hmac.compare_digest("café", "cafe")
except TypeError as e:
    print("TypeError:", e)
try:
    hmac.new(b"key", b"msg")
except TypeError as e:
    print("TypeError:", e)
