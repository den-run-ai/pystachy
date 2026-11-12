# error: _result() returns both bytes | None and str
# Text mode is decided when the call is compiled, by the types of text, universal_newlines,
# encoding and errors: an encoding that may be None would decide it as the program runs.
import subprocess


def f(encoding: str | None) -> None:
    print(subprocess.run(["sh", "-c", "echo x"], capture_output=True, encoding=encoding).stdout)


f("utf-8")
f(None)
