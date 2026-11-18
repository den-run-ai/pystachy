# error: expected bytes, got str
from librt.base64 import b64encode

print(b64encode("text"))
