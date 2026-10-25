# pystachy: dynamic-any
# tomllib over CPython 3.13.16's compliance corpus (Lib/test/test_tomllib/data): each file's
# result or TOMLDecodeError, printed for a differential comparison with CPython's own tomllib
import os
import tomllib

DATA = str(os.getenv("TOMLLIB_DATA")) + "/"  # Lib/test/test_tomllib/data of the 3.13.16 source
names = open("compliance_files.txt").read().split()
ok = 0
errors = 0
for name in names:
    with open(DATA + name) as f:
        text = f.read()
    try:
        doc = tomllib.loads(text)
        ok += 1
        print(name, "OK", repr(doc)[:3000])
    except tomllib.TOMLDecodeError as e:
        errors += 1
        print(name, "TOMLDecodeError", e)
print(ok, "parsed,", errors, "rejected")
