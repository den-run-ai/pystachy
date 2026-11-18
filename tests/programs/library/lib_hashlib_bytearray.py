# hashlib's constructors and update() take a bytearray: its bytes as they are at the call.
import hashlib
import hmac


def main() -> None:
    x = b"abc"
    print(bytes(x) is x)
    b = bytearray(b"The quick brown fox jumps over the lazy dog")
    print(hashlib.sha256(b).hexdigest(), hashlib.md5(b).hexdigest())
    print(hashlib.sha1(data=b).hexdigest(), hashlib.new("sha224", b).hexdigest())
    h = hashlib.sha256()
    h.update(b)
    b += b"."
    h.update(b)
    h.update(bytes(b))
    h.update(b"")
    h.update(bytearray())
    print(h.hexdigest())
    big = bytearray()
    for i in range(1000):
        big.append(i & 255)
    g = hashlib.sha1(big)
    big[0] = 9
    g.update(big)
    print(g.hexdigest())
    print(hmac.new(b"key", b"msg", hashlib.sha256).hexdigest())
    print(hmac.digest(b"key", b"msg", "md5").hex())
    fs = [hashlib.md5, hashlib.md5]
    print([f(b"x").hexdigest()[:8] for f in fs], list(map(hashlib.sha1, [b"y"]))[0].digest_size)
    u = h.update
    u(b"more")
    print(h.hexdigest()[:16])


main()
