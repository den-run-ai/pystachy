# stdout is closed when the program starts (tests/run.sh closes it for a program named
# *_closed_stdout), so CPython's sys.stdout is None: input() raises RuntimeError without reading
# stdin, with a prompt or without. The results go to stderr, whose last line tests/run.sh compares
import sys

seen = []
for prompt in ["", "prompt> "]:
    try:
        seen.append("got " + repr(input(prompt) if prompt else input()))
    except (RuntimeError, EOFError) as e:
        seen.append(type(e).__name__ + ": " + str(e))
sys.stderr.write("; ".join(seen) + "\n")
