# hashlib has MD5, SHA-1, SHA-224 and SHA-256 (lib/compatibility.md): algorithms_guaranteed names
# those four, where CPython's set also has SHA-384, SHA-512, SHA-3, SHAKE and BLAKE2, and new()
# raises ValueError for another algorithm's name, which CPython hashes with
import hashlib

print(sorted(hashlib.algorithms_guaranteed))
try:
    print(hashlib.new("sha512", b"abc").name)
except ValueError as e:
    print("ValueError:", e)
