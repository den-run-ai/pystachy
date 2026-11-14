# Text mode is decided when a call is compiled: run() and check_output() return str where the
# call passes text, universal_newlines, encoding or errors, and bytes where it passes none of
# them. CPython decides as it runs, from their values, so that text=False, universal_newlines=False
# and an empty encoding or errors are as none: it returns bytes (b'x\n' below). Here such a call
# is compiled to return str, and raises ValueError rather than return the wrong type.
import subprocess


def output(text: bool) -> str:
    return subprocess.check_output(["sh", "-c", "echo x"], text=text)


print(repr(output(True)))
try:
    print(repr(output(False)))
except ValueError as e:
    print("ValueError", e)
try:
    print(subprocess.run(["sh", "-c", "echo x"], capture_output=True, universal_newlines=False).stdout)
except ValueError as e:
    print("ValueError")
try:
    print(subprocess.run(["sh", "-c", "echo x"], capture_output=True, encoding="").stdout)
except ValueError as e:
    print("ValueError")
try:
    print(subprocess.call(["sh", "-c", "exit 0"], text=False, errors=""))
except ValueError as e:
    print("ValueError")
print(repr(subprocess.run(["sh", "-c", "echo x"], capture_output=True, text=False, encoding="utf-8").stdout))
