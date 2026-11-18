# error: cannot import name 'b32encode' from 'librt.base64'
from librt.base64 import b32encode

print(b32encode(b"hi"))
