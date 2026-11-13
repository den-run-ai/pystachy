# error: expected bytes, got str
# hmac's keys and messages are bytes (lib/compatibility.md): a str is a compile-time error, where
# CPython raises TypeError
import hmac

print(hmac.new("key", b"message", "sha256").hexdigest())
