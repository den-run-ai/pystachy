# subprocess.run(): exit statuses, both streams, input, the directory and the environment
import os
import subprocess
import sys

# the exit status, and nothing captured
done = subprocess.run(["sh", "-c", "exit 3"])
print(done.returncode, done.stdout, done.stderr, done.args)
print(done)
print(subprocess.run("exit 7", shell=True).returncode)
print(subprocess.run(["sh", "-c", "kill -9 $$"]).returncode)

# both streams, as bytes
done = subprocess.run(["sh", "-c", "echo out; echo err >&2; exit 1"], capture_output=True)
print(done.returncode, done.stdout, done.stderr)
print(done)
out = done.stdout
if out is not None:
    print(out.decode().upper(), len(out))

# one of them, the other with it, and neither
done = subprocess.run(["sh", "-c", "echo out; echo err >&2"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print(done.stdout, done.stderr)
done = subprocess.run(["sh", "-c", "echo out; echo err >&2"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
print(done.stdout, done.stderr)
done = subprocess.run(["sh", "-c", "echo out; echo err >&2"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
print(done.stdout, done.stderr)
done = subprocess.run(["sh", "-c", "read x; echo got $x"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
print(done.stdout)

# input
done = subprocess.run(["cat"], input=b"a\x00b\xff\n", capture_output=True)
print(done.stdout, done.stderr)
done = subprocess.run(["sh", "-c", "cat >&2"], input=b"", capture_output=True)
print(done.stdout, done.stderr)
big = b"0123456789abcdef" * 65536
done = subprocess.run(["cat"], input=big, stdout=subprocess.PIPE)
out = done.stdout
print(out == big, None if out is None else len(out))
done = subprocess.run(["sh", "-c", "cat >&2; echo done"], input=big, capture_output=True)
err = done.stderr
print(done.stdout, err == big)
# a child that does not read what it is sent
done = subprocess.run(["sh", "-c", "exit 0"], input=big, capture_output=True)
print(done.returncode, done.stdout)

# the directory and the environment
here = os.getcwd()
done = subprocess.run(["sh", "-c", "pwd"], cwd="/", capture_output=True)
print(done.stdout, os.getcwd() == here)
done = subprocess.run(["sh", "-c", "echo $A-$B-$HOME"], env={"A": "1", "B": "two words", "PATH": os.environ["PATH"]},
                      capture_output=True)
print(done.stdout)
os.environ["PYSTACHY_SUBPROCESS_TEST"] = "inherited"
print(subprocess.run(["sh", "-c", "echo $PYSTACHY_SUBPROCESS_TEST"], capture_output=True).stdout)
print(subprocess.run(["sh", "-c", "echo [$PYSTACHY_SUBPROCESS_TEST]"], env={"PATH": os.environ["PATH"]},
                     capture_output=True).stdout)
# the program is looked for in the PATH of env
try:
    subprocess.run(["sh", "-c", "echo found"], env={"PATH": "/nonexistent"})
except FileNotFoundError as e:
    print("FileNotFoundError", e)
print(subprocess.run(["/bin/sh", "-c", "echo found"], env={}, capture_output=True).stdout)

# the shell: a str is its command, a list its command and arguments
print(subprocess.run("echo $0 $1; echo two >&2", shell=True, capture_output=True).stdout)
print(subprocess.run(["echo $0 $1", "zero", "one"], shell=True, capture_output=True).stdout)
# without it a str is the program's name
try:
    subprocess.run("sh -c true")
except FileNotFoundError as e:
    print("FileNotFoundError", e)

# the child's standard output is the parent's
sys.stdout.flush()
subprocess.run(["sh", "-c", "echo to stdout"])
subprocess.run(["sh", "-c", "echo to stdout too >&2"], stderr=subprocess.STDOUT)
subprocess.run(["sh", "-c", "echo to stderr >&2"], stderr=subprocess.DEVNULL)
print(subprocess.call(["sh", "-c", "exit 4"]), subprocess.call("exit 5", shell=True, stdout=subprocess.DEVNULL))
print(subprocess.check_call(["sh", "-c", "exit 0"]))

# its signals are the defaults: a writer to a closed pipe ends, as it ends from a shell
done = subprocess.run(["sh", "-c", "(while :; do echo y; done) | (read x; echo $x)"], capture_output=True, timeout=30)
print(done.returncode, done.stdout, done.stderr)
