# error: expected bytes | None, got str
# CalledProcessError's output and stderr are bytes or None, also those of a call in text mode
# (tests/deviations/lib_subprocess_text_error.py): a str is not one.
import subprocess

e = subprocess.CalledProcessError(1, "x", "text")
print(e.output)
