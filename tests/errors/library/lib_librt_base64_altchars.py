# error: b64decode() takes 1 positional argument but 2 were given
from librt.base64 import b64decode

print(b64decode(b"aGk=", b"-_"))
