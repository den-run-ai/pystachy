# error: expected int | None, got file
# Popen's stdin, stdout and stderr are None or an int: PIPE, STDOUT, DEVNULL or a file
# descriptor. An open file's is its fileno(), which run(), call() and check_output() take of it.
import subprocess

with open("/dev/null", "w") as f:
    p = subprocess.Popen(["sh", "-c", "echo x"], stdout=f)
    print(p.wait())
