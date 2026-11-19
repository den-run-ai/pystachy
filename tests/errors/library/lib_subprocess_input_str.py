# error: expected bytes | None, got str
# input is bytes, and a str only in text mode (text, universal_newlines, encoding or errors),
# which is decided when the call is compiled. CPython raises TypeError as it writes the str.
import subprocess

print(subprocess.run(["cat"], input="text\n", capture_output=True).stdout)
