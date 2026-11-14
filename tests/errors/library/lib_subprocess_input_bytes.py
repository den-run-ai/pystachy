# error: 'bytes' has no method 'encode'
# In text mode input is a str, which run() encodes. CPython raises AttributeError for bytes.
import subprocess

print(subprocess.run(["cat"], input=b"bytes\n", capture_output=True, text=True).stdout)
