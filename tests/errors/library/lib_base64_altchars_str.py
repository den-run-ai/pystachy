# error: expected bytes | None, got str
import base64

print(base64.b64encode(b"x", altchars="-_"))
