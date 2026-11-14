# A CalledProcessError's output and stderr are bytes, also those of a call in text mode: the
# bytes that the child wrote, before they are decoded and their newlines translated. CPython's
# are then the str that the call would have returned ('out\n' and 'err\n' below). An exception's
# field has one type, and a union does not hold bytes; CPython's TimeoutExpired holds bytes in
# text mode too.
import subprocess

try:
    subprocess.run(["sh", "-c", "printf 'out\\r\\n'; echo err >&2; exit 3"], capture_output=True, text=True,
                   check=True)
except subprocess.CalledProcessError as e:
    print(e, e.output, e.stdout, e.stderr)
try:
    subprocess.check_output(["sh", "-c", "printf 'caf\\351\\n'; exit 1"], encoding="latin-1")
except subprocess.CalledProcessError as e:
    out = e.output
    print(out, None if out is None else out.decode("latin-1"))

# check_returncode() raises it with what run() captured
done = subprocess.run(["sh", "-c", "printf 'caf\\351\\r\\n'; exit 4"], stdout=subprocess.PIPE, encoding="latin-1")
print(repr(done.stdout), done.stderr)
try:
    done.check_returncode()
except subprocess.CalledProcessError as e:
    print(e, e.output, e.stderr)
# and, for a CompletedProcess that the program made of text, with the text as UTF-8
made = subprocess.CompletedProcess("made", 2, "café\n", "")
try:
    made.check_returncode()
except subprocess.CalledProcessError as e:
    print(e, e.output, e.stderr)
