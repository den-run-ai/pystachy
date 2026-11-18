# hmac hashes with lib/hashlib's MD5, SHA-1, SHA-224 and SHA-256 (lib/compatibility.md): another
# hash's name raises hashlib.new()'s ValueError, where CPython computes the HMAC with it.
import hmac

try:
    print(hmac.new(b"key", b"message", "sha512").hexdigest())
except ValueError as e:
    print("ValueError:", e)
