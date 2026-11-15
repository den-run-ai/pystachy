# error: module 'hashlib' has no attribute 'sha512'
# lib/hashlib has MD5, SHA-1, SHA-224 and SHA-256 (lib/compatibility.md): SHA-512's words are
# 64-bit, and Pystachy's int arithmetic is checked
import hashlib

print(hashlib.sha512(b"pystachy").hexdigest())
